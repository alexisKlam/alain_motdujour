#!/usr/bin/env python3
"""Local web manager for the Le mot du jour Hugo blog.

The app intentionally uses only Python's standard library so it can run on
macOS and Windows without a package installation step.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
import zipfile
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
CONTENT_DIR = REPO_ROOT / "content" / "post"
UPLOADS_DIR = REPO_ROOT / "static" / "wp-content" / "uploads"
FRONTPAGE_DATA = REPO_ROOT / "data" / "frontpage.json"
BACKUP_DIR = REPO_ROOT / ".blog-manager" / "backups"
WEB_DIR = APP_DIR / "web"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local blog manager.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), BlogManagerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Blog manager running at {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping blog manager.")


class BlogManagerHandler(BaseHTTPRequestHandler):
    server_version = "BlogManager/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path, query = self.parsed_path()
        try:
            if path == "/":
                self.serve_static(WEB_DIR / "index.html")
            elif path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
            elif path.startswith("/web/"):
                self.serve_static(WEB_DIR / path.removeprefix("/web/"))
            elif self.serve_blog_static(path):
                return
            elif path == "/api/articles":
                self.json_response({"articles": list_articles(), "frontpage": load_frontpage()})
            elif path == "/api/article":
                self.json_response(get_article(require_query(query, "path")))
            elif path == "/api/git/status":
                self.json_response({"files": git_status()})
            else:
                self.error_json("Not found.", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - intentionally reported to local user
            self.error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path, _query = self.parsed_path()
        try:
            if path == "/api/save_article":
                payload = self.read_json()
                self.json_response(save_article(payload))
            elif path == "/api/import_docx":
                fields, files = self.read_multipart()
                self.json_response(import_docx(files["file"], fields))
            elif path == "/api/import_media":
                fields, files = self.read_multipart()
                self.json_response(import_media(files["file"], fields))
            elif path == "/api/set_homepage":
                self.json_response(set_homepage(self.read_json()))
            elif path == "/api/build":
                self.json_response(run_command(["hugo", "--minify"], timeout=180))
            elif path == "/api/git/commit_push":
                self.json_response(commit_push(self.read_json()))
            else:
                self.error_json("Not found.", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - intentionally reported to local user
            self.error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def parsed_path(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, urllib.parse.parse_qs(parsed.query)

    def serve_static(self, path: Path) -> None:
        resolved = path.resolve()
        if not str(resolved).startswith(str(WEB_DIR.resolve())) or not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_blog_static(self, path: str) -> bool:
        relative = urllib.parse.unquote(path.lstrip("/"))
        if not relative:
            return False
        static_path = (REPO_ROOT / "static" / relative).resolve()
        static_root = (REPO_ROOT / "static").resolve()
        if static_path == static_root or static_root not in static_path.parents or not static_path.is_file():
            return False
        content_type = mimetypes.guess_type(str(static_path))[0] or "application/octet-stream"
        body = static_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8") or "{}")

    def read_multipart(self) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r'boundary="?([^";]+)"?', content_type)
        if not match:
            raise ValueError("Missing multipart boundary.")
        boundary = match.group(1).encode("utf-8")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        fields: dict[str, str] = {}
        files: dict[str, dict[str, Any]] = {}

        for raw_part in body.split(b"--" + boundary):
            part = raw_part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            raw_headers, separator, raw_content = part.partition(b"\r\n\r\n")
            if not separator:
                continue
            headers = parse_part_headers(raw_headers)
            disposition = headers.get("content-disposition", "")
            name = header_param(disposition, "name")
            filename = header_param(disposition, "filename")
            content = raw_content.removesuffix(b"\r\n")
            if not name:
                continue
            if filename:
                files[name] = {
                    "filename": Path(filename).name,
                    "content": content,
                    "content_type": headers.get("content-type", "application/octet-stream"),
                }
            else:
                fields[name] = content.decode("utf-8", errors="replace")
        return fields, files

    def json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error_json(self, message: str, status: HTTPStatus) -> None:
        self.json_response({"error": message}, status)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def require_query(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name) or []
    if not values:
        raise ValueError(f"Missing query parameter: {name}")
    return values[0]


def parse_part_headers(raw_headers: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw_headers.decode("utf-8", errors="replace").split("\r\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def header_param(header_value: str, name: str) -> str:
    pattern = rf'{re.escape(name)}="([^"]*)"|{re.escape(name)}=([^;]+)'
    match = re.search(pattern, header_value)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def list_articles() -> list[dict[str, Any]]:
    articles = []
    for path in sorted(CONTENT_DIR.glob("*.md"), reverse=True):
        meta, body, _ = read_markdown_file(path)
        title = str(meta.get("title") or path.stem)
        date_value = str(meta.get("date") or "")
        articles.append(
            {
                "path": repo_rel(path),
                "title": title,
                "date": date_value,
                "permalink": permalink_for(path),
                "categories": meta.get("categories") or [],
                "tags": meta.get("tags") or [],
                "excerpt": plain_excerpt(body),
                "modified": int(path.stat().st_mtime),
            }
        )
    articles.sort(key=lambda item: item["date"], reverse=True)
    return articles


def get_article(path_value: str) -> dict[str, Any]:
    path = safe_repo_path(path_value)
    meta, body, delimiter = read_markdown_file(path)
    return {
        "path": repo_rel(path),
        "delimiter": delimiter,
        "meta": meta,
        "content": body,
        "permalink": permalink_for(path),
    }


def save_article(payload: dict[str, Any]) -> dict[str, Any]:
    path_value = str(payload.get("path") or "")
    incoming_meta = payload.get("meta") or {}
    content = str(payload.get("content") or "")
    create_new = not path_value

    if create_new:
        meta = incoming_meta
        title = str(meta.get("title") or "Nouvel article")
        date_value = str(meta.get("date") or date.today().isoformat())
        path = CONTENT_DIR / f"{date_value[:10]}-{slugify(title)[:60]}.md"
        path = unique_path(path)
    else:
        path = safe_repo_path(path_value)
        existing_meta, _existing_body, _delimiter = read_markdown_file(path)
        meta = {**existing_meta, **incoming_meta}
        backup_file(path)

    normalized_meta = normalize_meta(meta, path)
    path.write_text(render_markdown(normalized_meta, content), encoding="utf-8")
    return {"ok": True, "article": get_article(repo_rel(path))}


def import_media(file_info: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    target_date = parse_date(fields.get("date")) or date.today()
    url = save_media(file_info["filename"], file_info["content"], target_date)
    return {"ok": True, "url": url}


def import_docx(file_info: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    target_date = parse_date(fields.get("date")) or date.today()
    title = fields.get("title") or Path(file_info["filename"]).stem.replace("-", " ").strip()
    markdown = docx_to_markdown(file_info["content"], target_date)
    meta = {
        "title": title,
        "author": "alain",
        "type": "post",
        "date": target_date.isoformat() + "T00:00:00+00:00",
        "categories": ["Mot du jour"],
        "tags": [],
    }
    path = unique_path(CONTENT_DIR / f"{target_date.isoformat()}-{slugify(title)[:60]}.md")
    path.write_text(render_markdown(meta, markdown), encoding="utf-8")
    return {"ok": True, "article": get_article(repo_rel(path))}


def set_homepage(payload: dict[str, Any]) -> dict[str, Any]:
    use_default = bool(payload.get("default"))
    FRONTPAGE_DATA.parent.mkdir(parents=True, exist_ok=True)
    if use_default:
        data = {"permalink": "", "mode": "latest"}
    else:
        path = safe_repo_path(str(payload.get("path") or ""))
        data = {"permalink": permalink_for(path), "mode": "manual", "path": repo_rel(path)}
    FRONTPAGE_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "frontpage": data}


def load_frontpage() -> dict[str, str]:
    if not FRONTPAGE_DATA.exists():
        return {"permalink": "", "mode": "latest"}
    return json.loads(FRONTPAGE_DATA.read_text(encoding="utf-8"))


def commit_push(payload: dict[str, Any]) -> dict[str, Any]:
    files = [str(item) for item in payload.get("files") or []]
    message = str(payload.get("message") or "").strip()
    do_push = bool(payload.get("push"))
    if not files:
        raise ValueError("Select at least one file to commit.")
    if not message:
        raise ValueError("Commit message is required.")
    for item in files:
        safe_repo_path(item, must_exist=False)
    git_add = run_command(["git", "add", "--", *files], timeout=60)
    git_commit = run_command(["git", "commit", "-m", message], timeout=120)
    result = {"add": git_add, "commit": git_commit}
    if do_push:
        result["push"] = run_command(["git", "push"], timeout=180)
    result["status"] = git_status()
    return result


def git_status() -> list[dict[str, str]]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    files = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        files.append({"status": line[:2], "path": line[3:]})
    return files


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
        "command": command,
    }


def read_markdown_file(path: Path) -> tuple[dict[str, Any], str, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return parse_frontmatter(text[4:end]), text[end + 4 :].lstrip("\n"), "---"
    if text.startswith("+++\n"):
        end = text.find("\n+++", 4)
        if end != -1:
            return parse_toml_like(text[4:end]), text[end + 4 :].lstrip("\n"), "+++"
    return {}, text, "---"


def parse_frontmatter(raw: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    current_key = ""
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(unquote_scalar(line[4:].strip()))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value == "":
            meta[current_key] = []
        else:
            meta[current_key] = unquote_scalar(value)
    return meta


def parse_toml_like(raw: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        meta[key.strip()] = unquote_scalar(value.strip())
    return meta


def unquote_scalar(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def render_markdown(meta: dict[str, Any], content: str) -> str:
    lines = ["---"]
    for key in ["title", "author", "type", "date", "draft", "aliases", "categories", "tags"]:
        if key not in meta or meta[key] in (None, "", []):
            continue
        value = meta[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(str(item))}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {yaml_scalar(str(value))}")
    for key, value in meta.items():
        if key in {"title", "author", "type", "date", "draft", "aliases", "categories", "tags"}:
            continue
        lines.append(f"{key}: {yaml_scalar(str(value))}")
    lines.extend(["", "---", content.lstrip("\n")])
    return "\n".join(lines).rstrip() + "\n"


def yaml_scalar(value: str) -> str:
    if value == "" or value.startswith(("{", "[", "#")) or ": " in value:
        return json.dumps(value, ensure_ascii=False)
    return value


def normalize_meta(meta: dict[str, Any], path: Path) -> dict[str, Any]:
    normalized = dict(meta)
    normalized["title"] = str(normalized.get("title") or path.stem)
    normalized["author"] = str(normalized.get("author") or "alain")
    normalized["type"] = str(normalized.get("type") or "post")
    normalized["date"] = str(normalized.get("date") or date.today().isoformat() + "T00:00:00+00:00")
    for key in ["aliases", "categories", "tags"]:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = [item.strip() for item in value.split(",") if item.strip()]
        elif not isinstance(value, list):
            normalized[key] = []
    return normalized


def docx_to_markdown(content: bytes, target_date: date) -> str:
    with zipfile.ZipFile(io_bytes(content)) as docx:
        rels = parse_docx_relationships(docx)
        document = ET.fromstring(docx.read("word/document.xml"))
        parts: list[str] = []
        for paragraph in document.findall(".//w:body/w:p", NS):
            text = docx_paragraph_to_markdown(docx, paragraph, rels, target_date)
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip() + "\n"


def io_bytes(content: bytes):
    import io

    return io.BytesIO(content)


def parse_docx_relationships(docx: zipfile.ZipFile) -> dict[str, str]:
    rels: dict[str, str] = {}
    try:
        root = ET.fromstring(docx.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rels[rel_id] = target
    return rels


def docx_paragraph_to_markdown(docx: zipfile.ZipFile, paragraph: ET.Element, rels: dict[str, str], target_date: date) -> str:
    style = paragraph.find("w:pPr/w:pStyle", NS)
    style_value = style.attrib.get(f"{{{NS['w']}}}val", "") if style is not None else ""
    chunks: list[str] = []
    for run in paragraph.findall("w:r", NS):
        chunks.append(docx_run_to_markdown(docx, run, rels, target_date))
    text = "".join(chunks).strip()
    if not text:
        return ""
    if style_value.lower().startswith("heading1") or style_value == "Titre1":
        return "# " + text
    if style_value.lower().startswith("heading2") or style_value == "Titre2":
        return "## " + text
    if style_value.lower().startswith("heading3") or style_value == "Titre3":
        return "### " + text
    return text


def docx_run_to_markdown(docx: zipfile.ZipFile, run: ET.Element, rels: dict[str, str], target_date: date) -> str:
    image = run.find(".//a:blip", NS)
    if image is not None:
        rel_id = image.attrib.get(f"{{{NS['r']}}}embed")
        target = rels.get(rel_id or "")
        if target:
            source = "word/" + target.lstrip("/")
            try:
                data = docx.read(source)
            except KeyError:
                data = b""
            if data:
                url = save_media(Path(target).name, data, target_date)
                return f"\n\n![Image importée]({url})\n\n"
    text = "".join(node.text or "" for node in run.findall("w:t", NS))
    if not text:
        return ""
    props = run.find("w:rPr", NS)
    if props is not None:
        if props.find("w:b", NS) is not None:
            text = f"**{text}**"
        if props.find("w:i", NS) is not None:
            text = f"*{text}*"
    return text


def save_media(filename: str, content: bytes, target_date: date) -> str:
    month_dir = UPLOADS_DIR / f"{target_date.year:04d}" / f"{target_date.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)
    safe_name = slugify(Path(filename).stem) or "media"
    suffix = Path(filename).suffix.lower()
    target = unique_path(month_dir / f"{safe_name}{suffix}")
    target.write_bytes(content)
    return "/" + repo_rel(target).removeprefix("static/")


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / repo_rel(path)
    target = target.with_name(f"{target.stem}.{stamp}{target.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def safe_repo_path(path_value: str, must_exist: bool = True) -> Path:
    if not path_value:
        raise ValueError("Missing path.")
    path = (REPO_ROOT / path_value).resolve()
    root = REPO_ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError("Path outside repository.")
    if must_exist and not path.exists():
        raise ValueError(f"Path does not exist: {path_value}")
    return path


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def permalink_for(path: Path) -> str:
    if path.parent == CONTENT_DIR:
        return f"/post/{path.stem}/"
    return "/" + repo_rel(path)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Could not find available filename for {path}")


def slugify(value: str) -> str:
    value = value.lower()
    accents = str.maketrans("àâäéèêëîïôöùûüçœ", "aaaeeeeiioouuucœ")
    value = value.translate(accents).replace("œ", "oe")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def plain_excerpt(markdown: str) -> str:
    text = re.sub(r"<[^>]+>", " ", markdown)
    text = re.sub(r"[#*_>`\[\]()]|!\[[^\]]*\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]


if __name__ == "__main__":
    main()
