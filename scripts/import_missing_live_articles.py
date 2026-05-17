#!/usr/bin/env python3
"""Import published WordPress posts that are missing from the Hugo checkout.

The script compares live WordPress post IDs with local Hugo aliases such as
`/post/16757`, writes missing posts under content/post/YYYY-MM-DD.md, downloads
referenced /wp-content/uploads files under static/, and emits a markdown report.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen


SITE = "https://lemotdujour.fr"
REST_BASE = f"{SITE}/?rest_route=/wp/v2"
USER_AGENT = "BlogAlain-missing-post-importer/1.0"
UPLOAD_RE = re.compile(
    r"(?:https?:)?//(?:www\.)?lemotdujour\.fr/(?P<absolute>wp-content/uploads/[^\"'\s<>,)]+)"
    r"|(?P<relative>/wp-content/uploads/[^\"'\s<>,)]+)"
)
POST_ALIAS_RE = re.compile(r"^\s*-\s*/post/(?P<id>\d+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ImportedPost:
    post_id: int
    title: str
    date: str
    source_url: str
    content_path: Path
    downloads: int
    failed_downloads: tuple[str, ...]


def fetch_json(url: str, timeout: float) -> tuple[Any, dict[str, str]]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        headers = {key.lower(): value for key, value in response.headers.items()}
        return json.load(response), headers


def fetch_all(endpoint: str, timeout: float, fields: str | None = None) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        url = f"{REST_BASE}/{endpoint}&per_page=100&page={page}"
        if fields:
            url += f"&_fields={fields}"
        data, headers = fetch_json(url, timeout)
        if not data:
            break
        items.extend(data)
        total_pages = int(headers.get("x-wp-totalpages", "1"))
        if page >= total_pages:
            break
        page += 1
    return items


def local_post_ids(content_root: Path) -> set[int]:
    ids: set[int] = set()
    for path in sorted(content_root.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        ids.update(int(match.group("id")) for match in POST_ALIAS_RE.finditer(text))
    return ids


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n".join(f"  - {yaml_scalar(value)}" for value in values)


def post_filename(date_value: str, post_id: int, existing_paths: set[Path]) -> Path:
    date_part = date_value[:10]
    candidate = Path(f"{date_part}.md")
    if candidate not in existing_paths:
        return candidate
    candidate = Path(f"{date_part}-{post_id}.md")
    return candidate


def normalize_upload_url(raw_url: str) -> str:
    raw_url = html.unescape(raw_url.strip())
    parts = urlsplit(raw_url)
    if parts.scheme in ("http", "https") and parts.netloc in {"lemotdujour.fr", "www.lemotdujour.fr"}:
        path = parts.path
    elif raw_url.startswith("//lemotdujour.fr/") or raw_url.startswith("//www.lemotdujour.fr/"):
        path = urlsplit(f"https:{raw_url}").path
    else:
        path = raw_url.split("#", 1)[0].split("?", 1)[0]
    return unquote(path)


def localize_content(content: str) -> str:
    content = html.unescape(content)
    content = re.sub(r"https?://(?:www\.)?lemotdujour\.fr/wp-content/uploads/", "/wp-content/uploads/", content)
    content = re.sub(r"//(?:www\.)?lemotdujour\.fr/wp-content/uploads/", "/wp-content/uploads/", content)
    return content.strip()


def iter_upload_paths(content: str) -> list[str]:
    paths: set[str] = set()
    for match in UPLOAD_RE.finditer(content):
        value = match.group("absolute") or match.group("relative")
        if not value:
            continue
        if value.startswith("/"):
            value = value.lstrip("/")
        paths.add(normalize_upload_url("/" + value).lstrip("/"))
    return sorted(paths)


def remote_upload_url(upload_path: str) -> str:
    parts = [quote(part) for part in upload_path.split("/")]
    return f"{SITE}/{'/'.join(parts)}"


def download_upload(root: Path, upload_path: str, timeout: float, dry_run: bool) -> bool:
    target = root / "static" / upload_path
    if target.exists():
        return False
    if dry_run:
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(remote_upload_url(upload_path), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        target.write_bytes(response.read())
    return True


def taxonomy_map(endpoint: str, timeout: float) -> dict[int, str]:
    items = fetch_all(endpoint, timeout, fields="id,name")
    return {int(item["id"]): strip_html(item["name"]) for item in items}


def render_post(post: dict[str, Any], category_names: dict[int, str], tag_names: dict[int, str]) -> str:
    title = strip_html(post["title"]["rendered"])
    date_part = post["date"][:10]
    categories = [category_names.get(int(category_id), str(category_id)) for category_id in post.get("categories", [])]
    tags = [tag_names.get(int(tag_id), str(tag_id)) for tag_id in post.get("tags", [])]
    content = localize_content(post["content"]["rendered"])

    frontmatter = [
        "---",
        f"title: {yaml_scalar(title)}",
        "author: alain",
        "type: post",
        f"date: {date_part}T00:00:00+00:00",
        "aliases:",
        f"  - /post/{post['id']}",
        "categories:",
        yaml_list(categories),
        "tags:",
        yaml_list(tags),
        "",
        "---",
    ]
    return "\n".join(frontmatter) + "\n" + content + "\n"


def write_report(root: Path, imported: list[ImportedPost], skipped_count: int, dry_run: bool) -> Path:
    report_path = root / "reports" / "missing-live-articles-report.md"
    lines = [
        "# Missing Live Articles Import Report",
        "",
        f"- Source: {SITE}",
        f"- Mode: {'dry-run' if dry_run else 'write'}",
        f"- Existing local WordPress post IDs skipped: {skipped_count}",
        f"- Articles added: {len(imported)}",
        "",
        "| ID | Date | Title | Local file | Downloads | Failed downloads |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in imported:
        lines.append(
            "| {id} | {date} | {title} | {path} | {downloads} | {failed} |".format(
                id=item.post_id,
                date=item.date,
                title=item.title.replace("|", "\\|"),
                path=item.content_path.as_posix(),
                downloads=item.downloads,
                failed=len(item.failed_downloads),
            )
        )
    failed = [(item, url) for item in imported for url in item.failed_downloads]
    if failed:
        lines.extend(["", "## Failed Downloads", ""])
        for item, url in failed:
            lines.append(f"- `{item.content_path}`: `{url}`")

    if not dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def import_missing(root: Path, timeout: float, dry_run: bool) -> tuple[list[ImportedPost], int, Path]:
    content_root = root / "content" / "post"
    existing_ids = local_post_ids(content_root)
    existing_paths = {path.relative_to(content_root) for path in content_root.glob("*.md")}

    posts = fetch_all(
        "posts",
        timeout,
        fields="id,date,slug,link,title,content,categories,tags,featured_media",
    )
    category_names = taxonomy_map("categories", timeout)
    tag_names = taxonomy_map("tags", timeout)
    missing = [post for post in posts if int(post["id"]) not in existing_ids]
    missing.sort(key=lambda post: post["date"])

    imported: list[ImportedPost] = []
    for post in missing:
        post_id = int(post["id"])
        relative_path = post_filename(post["date"], post_id, existing_paths)
        existing_paths.add(relative_path)
        content_path = content_root / relative_path
        rendered = render_post(post, category_names, tag_names)
        upload_paths = iter_upload_paths(rendered)

        downloads = 0
        failed_downloads: list[str] = []
        for upload_path in upload_paths:
            try:
                if download_upload(root, upload_path, timeout, dry_run):
                    downloads += 1
                time.sleep(0.05)
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                failed_downloads.append(f"{upload_path} ({type(error).__name__}: {error})")

        if not dry_run:
            content_path.write_text(rendered, encoding="utf-8")

        imported.append(
            ImportedPost(
                post_id=post_id,
                title=strip_html(post["title"]["rendered"]),
                date=post["date"][:10],
                source_url=post["link"],
                content_path=content_path.relative_to(root),
                downloads=downloads,
                failed_downloads=tuple(failed_downloads),
            )
        )

    report_path = write_report(root, imported, len(posts) - len(missing), dry_run)
    return imported, len(posts), report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        imported, live_count, report_path = import_missing(root, args.timeout, args.dry_run)
    except Exception as error:
        print(f"Import failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    print(f"Live published posts: {live_count}")
    print(f"Articles added: {len(imported)}")
    print(f"Report: {report_path.relative_to(root)}")
    for item in imported:
        print(
            f"{item.date}\t{item.post_id}\t{item.content_path}\t"
            f"downloads={item.downloads}\tfailed={len(item.failed_downloads)}\t{item.title}"
        )
    return 1 if any(item.failed_downloads for item in imported) else 0


if __name__ == "__main__":
    raise SystemExit(main())
