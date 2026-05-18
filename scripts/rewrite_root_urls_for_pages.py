#!/usr/bin/env python3
"""Rewrite root-relative generated URLs for GitHub Pages project sites.

WordPress-imported article HTML often contains assets such as
`/wp-content/uploads/...`. Those URLs work on a root domain, but GitHub Pages
project sites are served below `/<repo>/`, so the generated `public/` files need
the project base path inserted after Hugo has rendered the raw article HTML.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit


TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".txt",
    ".webmanifest",
    ".xml",
}

LOCAL_PREFIXES = (
    "categories",
    "css",
    "js",
    "page",
    "post",
    "sitemap.xml",
    "tags",
    "wp-content",
)


def base_path_from_url(base_url: str) -> str:
    path = urlsplit(base_url).path.strip("/")
    if not path:
        return ""
    return "/" + path


def rewrite_text(text: str, base_path: str) -> tuple[str, int]:
    if not base_path:
        return text, 0

    prefixes = "|".join(re.escape(prefix) for prefix in LOCAL_PREFIXES)
    pattern = re.compile(
        rf"(?P<prefix>[=(\"']|,\s*)/(?P<target>(?:{prefixes})(?:[/?#][^\"'\s),<>]*)?)"
    )

    def replace(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{base_path}/{match.group('target')}"

    return pattern.subn(replace, text)


def iter_text_files(public_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(public_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_dir", type=Path, help="Generated Hugo public directory")
    parser.add_argument("base_url", help="Final site base URL, for example the GitHub Pages URL")
    parser.add_argument("--dry-run", action="store_true", help="Report files without writing changes")
    args = parser.parse_args()

    public_dir = args.public_dir.resolve()
    if not public_dir.exists():
        parser.error(f"{public_dir} does not exist")

    base_path = base_path_from_url(args.base_url)
    changed_files = 0
    replacements = 0

    for path in iter_text_files(public_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        rewritten, count = rewrite_text(text, base_path)
        if count == 0:
            continue
        changed_files += 1
        replacements += count
        if not args.dry_run:
            path.write_text(rewritten, encoding="utf-8")

    mode = "would rewrite" if args.dry_run else "rewrote"
    print(f"{mode} files: {changed_files}")
    print(f"replacements: {replacements}")
    print(f"base path: {base_path or '/'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
