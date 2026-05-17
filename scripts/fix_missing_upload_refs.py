#!/usr/bin/env python3
"""Fix broken /wp-content/uploads references in converted Hugo content.

The WordPress export often kept srcset entries for resized thumbnails that are
not present in static/. When a browser selects one of those missing candidates,
the image appears broken even though the full-size src exists.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote


UPLOAD_PREFIX = "/wp-content/uploads/"
URL_RE = re.compile(r"(?<![A-Za-z0-9])/wp-content/uploads/[^\"'\s<>,)]+")
SRCSET_RE = re.compile(r'\s+srcset=(["\'])(.*?)\1', re.DOTALL)
RESIZED_RE = re.compile(r"^(?P<stem>.+)-(?P<size>\d+x\d+)(?P<suffix>\.[A-Za-z0-9]+)$")


def existing_path(static_root: Path, url: str) -> Path | None:
    """Return an existing local path for a URL, trying common encoding forms."""
    raw = html.unescape(url.split("#", 1)[0].split("?", 1)[0])
    if not raw.startswith(UPLOAD_PREFIX):
        return None

    relative = raw.lstrip("/")
    candidates = [
        relative,
        unquote(relative),
        unicodedata.normalize("NFC", unquote(relative)),
        unicodedata.normalize("NFD", unquote(relative)),
    ]

    for candidate in candidates:
        path = static_root / candidate
        if path.exists():
            return path
    return None


def url_exists(static_root: Path, url: str) -> bool:
    return existing_path(static_root, url) is not None


def resized_original_url(static_root: Path, url: str) -> str | None:
    """Map a missing WordPress thumbnail URL to its full-size image when present."""
    raw = html.unescape(url.split("#", 1)[0].split("?", 1)[0])
    path = Path(unquote(raw))
    match = RESIZED_RE.match(path.name)
    if not match:
        return None

    original_name = f"{match.group('stem')}{match.group('suffix')}"
    original_url = str(path.with_name(original_name)).replace("\\", "/")
    if url_exists(static_root, original_url):
        return original_url
    return None


def sibling_fallback_url(static_root: Path, url: str) -> str | None:
    """Find a nearby file with a common converted-image suffix."""
    raw = html.unescape(url.split("#", 1)[0].split("?", 1)[0])
    path = Path(unquote(raw))
    suffixes = ("_thumb", "-thumb")

    for suffix in suffixes:
        candidate_url = str(path.with_name(f"{path.stem}{suffix}{path.suffix}")).replace("\\", "/")
        if url_exists(static_root, candidate_url):
            return candidate_url
    return None


def fixed_url(static_root: Path, url: str) -> str:
    """Fix a normal src/href URL when a deterministic replacement exists."""
    if url_exists(static_root, url):
        return url

    original = resized_original_url(static_root, url)
    if original:
        return original

    fallback = sibling_fallback_url(static_root, url)
    if fallback:
        return fallback

    raw = html.unescape(url)
    decoded = unquote(raw)
    for normalized in (unicodedata.normalize("NFC", decoded), unicodedata.normalize("NFD", decoded)):
        if normalized != url and url_exists(static_root, normalized):
            return normalized

    return url


def fix_srcsets(text: str, static_root: Path, stats: dict[str, int]) -> str:
    def replace_srcset(match: re.Match[str]) -> str:
        quote = match.group(1)
        value = match.group(2)
        kept: list[str] = []

        for raw_candidate in value.split(","):
            candidate = raw_candidate.strip()
            if not candidate:
                continue

            parts = candidate.split()
            url = parts[0]
            descriptor = " ".join(parts[1:])

            if url_exists(static_root, url):
                kept.append(candidate)
                continue

            if resized_original_url(static_root, url):
                stats["removed_srcset_candidates"] += 1
                continue

            fixed = fixed_url(static_root, url)
            if fixed != url and url_exists(static_root, fixed):
                rebuilt = fixed if not descriptor else f"{fixed} {descriptor}"
                kept.append(rebuilt)
                stats["fixed_srcset_candidates"] += 1
                continue

            stats["removed_srcset_candidates"] += 1

        if not kept:
            stats["removed_srcset_attributes"] += 1
            return ""

        replacement = f" srcset={quote}{', '.join(kept)}{quote}"
        if replacement != match.group(0):
            stats["changed_srcset_attributes"] += 1
        return replacement

    return SRCSET_RE.sub(replace_srcset, text)


def fix_urls(text: str, static_root: Path, stats: dict[str, int], missing: set[str]) -> str:
    def replace_url(match: re.Match[str]) -> str:
        url = match.group(0)
        fixed = fixed_url(static_root, url)
        if fixed != url:
            stats["fixed_urls"] += 1
        elif not url_exists(static_root, url):
            stats["remaining_missing_urls"] += 1
            missing.add(url)
        return fixed

    return URL_RE.sub(replace_url, text)


def process_file(path: Path, static_root: Path, dry_run: bool) -> tuple[bool, dict[str, int], set[str]]:
    original = path.read_text(encoding="utf-8")
    stats = {
        "changed_srcset_attributes": 0,
        "fixed_srcset_candidates": 0,
        "removed_srcset_candidates": 0,
        "removed_srcset_attributes": 0,
        "fixed_urls": 0,
        "remaining_missing_urls": 0,
    }
    missing: set[str] = set()

    fixed = fix_srcsets(original, static_root, stats)
    fixed = fix_urls(fixed, static_root, stats, missing)

    changed = fixed != original
    if changed and not dry_run:
        path.write_text(fixed, encoding="utf-8")

    return changed, stats, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()

    root = args.root.resolve()
    content_root = root / "content"
    static_root = root / "static"

    if not content_root.exists() or not static_root.exists():
        print(f"Expected content/ and static/ under {root}", file=sys.stderr)
        return 2

    changed_files: list[Path] = []
    totals = {
        "changed_srcset_attributes": 0,
        "fixed_srcset_candidates": 0,
        "removed_srcset_candidates": 0,
        "removed_srcset_attributes": 0,
        "fixed_urls": 0,
        "remaining_missing_urls": 0,
    }
    missing_by_file: dict[Path, set[str]] = {}

    for path in sorted(content_root.rglob("*.md")):
        changed, stats, missing = process_file(path, static_root, args.dry_run)
        for key, value in stats.items():
            totals[key] += value
        if changed:
            changed_files.append(path)
        if missing:
            missing_by_file[path] = missing

    mode = "Would update" if args.dry_run else "Updated"
    print(f"{mode} {len(changed_files)} content files")
    for path in changed_files:
        print(path.relative_to(root))
    for key, value in totals.items():
        print(f"{key}: {value}")
    if missing_by_file:
        print("remaining missing references:")
        for path, urls in sorted(missing_by_file.items()):
            joined = ", ".join(sorted(urls))
            print(f"{path.relative_to(root)}: {joined}")

    return 1 if totals["remaining_missing_urls"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
