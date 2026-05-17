#!/usr/bin/env python3
"""Verify generated Hugo links and image references.

By default this checks local/internal links and images in public/**/*.html.
External HTTP(S) links are reported only when --check-external is used.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


INTERNAL_HOSTS = {"lemotdujour.fr", "www.lemotdujour.fr", "localhost", "127.0.0.1"}
ATTR_RE = re.compile(r'\b(?P<attr>href|src)=["\'](?P<value>[^"\']+)["\']', re.IGNORECASE)
SRCSET_RE = re.compile(r'\bsrcset=["\'](?P<value>[^"\']+)["\']', re.IGNORECASE | re.DOTALL)
CANONICAL_ARTICLE_RE = re.compile(r"post/\d{4}-\d{2}-\d{2}/index\.html$")
SKIP_SCHEMES = {"mailto", "tel", "javascript", "data"}


@dataclass(frozen=True)
class Problem:
    page: Path
    kind: str
    target: str
    reason: str


def public_target(public_root: Path, page: Path, target: str) -> Path | None:
    value = html.unescape(target.strip())
    if not value or value.startswith("#"):
        return None

    split = urlsplit(value)
    if split.scheme in SKIP_SCHEMES:
        return None
    if split.scheme in ("http", "https"):
        if split.netloc not in INTERNAL_HOSTS:
            return None
        value = split.path or "/"
    elif split.scheme:
        return None

    if value.startswith("//"):
        return None

    path_only = unquote(value.split("#", 1)[0].split("?", 1)[0])
    if not path_only:
        path_only = "/"

    if path_only.startswith("/"):
        route = path_only.lstrip("/")
    else:
        page_dir = page.parent.relative_to(public_root)
        route = str((page_dir / path_only)).replace("\\", "/")

    candidate = public_root / route
    return candidate


def target_exists(public_root: Path, page: Path, target: str) -> bool:
    candidate = public_target(public_root, page, target)
    if candidate is None:
        return True
    candidates = [candidate]
    if candidate.suffix == "":
        candidates.append(candidate / "index.html")
        candidates.append(candidate.with_suffix(".html"))
    return any(path.exists() for path in candidates)


def iter_srcset_urls(value: str) -> Iterable[str]:
    for raw_candidate in value.split(","):
        candidate = raw_candidate.strip()
        if candidate:
            yield candidate.split()[0]


def check_external(url: str, timeout: float) -> str | None:
    request = Request(url, method="HEAD", headers={"User-Agent": "BlogAlain-link-checker/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status < 400:
                return None
            return f"HTTP {response.status}"
    except Exception as head_error:
        try:
            request = Request(url, method="GET", headers={"User-Agent": "BlogAlain-link-checker/1.0"})
            with urlopen(request, timeout=timeout) as response:
                if response.status < 400:
                    return None
                return f"HTTP {response.status}"
        except Exception as get_error:
            return f"{type(get_error).__name__}: {get_error} (HEAD: {type(head_error).__name__})"


def is_absolute_internal(target: str) -> bool:
    split = urlsplit(html.unescape(target.strip()))
    return split.scheme in ("http", "https") and split.netloc in INTERNAL_HOSTS


def verify_page(
    public_root: Path,
    page: Path,
    check_external_links: bool,
    forbid_absolute_internal: bool,
    timeout: float,
) -> list[Problem]:
    text = page.read_text(encoding="utf-8", errors="replace")
    problems: list[Problem] = []

    for match in ATTR_RE.finditer(text):
        attr = match.group("attr").lower()
        target = html.unescape(match.group("value"))
        split = urlsplit(target)

        if forbid_absolute_internal and is_absolute_internal(target):
            problems.append(Problem(page, attr, target, "absolute internal URL"))

        if split.scheme in ("http", "https") and split.netloc not in INTERNAL_HOSTS:
            if check_external_links:
                reason = check_external(target, timeout)
                if reason:
                    problems.append(Problem(page, attr, target, reason))
            continue

        if not target_exists(public_root, page, target):
            problems.append(Problem(page, attr, target, "missing local target"))

    for match in SRCSET_RE.finditer(text):
        for target in iter_srcset_urls(html.unescape(match.group("value"))):
            if forbid_absolute_internal and is_absolute_internal(target):
                problems.append(Problem(page, "srcset", target, "absolute internal URL"))
            if not target_exists(public_root, page, target):
                problems.append(Problem(page, "srcset", target, "missing local target"))

    return problems


def is_alias_page(text: str) -> bool:
    return "http-equiv=\"refresh\"" in text or "http-equiv=refresh" in text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--public", type=Path, default=None, help="Generated public directory")
    parser.add_argument("--articles-only", action="store_true", help="Only scan public/post/**/*.html")
    parser.add_argument("--check-external", action="store_true", help="Also check external HTTP(S) links")
    parser.add_argument(
        "--allow-absolute-internal",
        action="store_true",
        help="Do not fail on absolute lemotdujour.fr URLs in generated pages",
    )
    parser.add_argument("--timeout", type=float, default=8.0, help="External link timeout in seconds")
    args = parser.parse_args()

    root = args.root.resolve()
    public_root = (args.public or root / "public").resolve()
    if not public_root.exists():
        print(f"{public_root} does not exist. Run `hugo` first.", file=sys.stderr)
        return 2

    pages = sorted(public_root.glob("**/*.html"))
    if args.articles_only:
        pages = [page for page in pages if CANONICAL_ARTICLE_RE.match(str(page.relative_to(public_root)).replace("\\", "/"))]
    problems: list[Problem] = []

    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        if is_alias_page(text):
            continue
        problems.extend(
            verify_page(
                public_root,
                page,
                args.check_external,
                not args.allow_absolute_internal,
                args.timeout,
            )
        )

    print(f"checked pages: {len(pages)}")
    print(f"problems: {len(problems)}")
    for problem in problems:
        rel_page = problem.page.relative_to(public_root)
        print(f"{rel_page}\t{problem.kind}\t{problem.target}\t{problem.reason}")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
