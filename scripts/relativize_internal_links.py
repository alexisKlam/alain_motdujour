#!/usr/bin/env python3
"""Rewrite absolute lemotdujour.fr URLs in source files to relative URLs.

Legacy WordPress query URLs are resolved through generated Hugo aliases when
possible, e.g. https://lemotdujour.fr/?p=512 -> /post/512/.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


INTERNAL_HOSTS = {"lemotdujour.fr", "www.lemotdujour.fr"}
ABSOLUTE_INTERNAL_RE = re.compile(r"https?://(?:www\.)?lemotdujour\.fr[^\s\"'<>)]*")
MALFORMED_LEGACY_P_ATTR_RE = re.compile(
    r'(?P<prefix>\bhref=["\'])https?://(?:www\.)?lemotdujour\.fr/\?p=\s*(?P<id>\d+)(?:\s*(?:=|<span=)?)?(?P<quote>["\'])',
    re.IGNORECASE,
)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r'\b(?P<name>[\w:-]+)=["\'](?P<value>[^"\']*)["\']', re.IGNORECASE)
HTML_ENTITY_SUFFIXES = ("&quot;", "&#34;", "&amp;quot;")

LEGACY_PAGE_ROUTES = {
    "1758": "/page/quelques-mots-sur-lauteur/",
    "2283": "/post/",
    "2537": "/page/la-violence-faite-aux-femmes-dans-lespace-public/",
    "2543": "/page/series-de-mots/",
    "2658": "/page/sapiens-de-yuval-noah-harari/",
    "2704": "/page/daniel-cohen-homo-oeconomicus-et-la-stagnation-seculaire/",
    "2739": "/page/regis-debray-la-croyance-et-le-sacre/",
    "2804": "/page/florence-aubenas-en-france-chroniques-dans-les-villes-et-villages-de-france/",
    "3467": "/page/la-meritocratie/",
    "4400": "/page/martin-luther-le-debut-de-la-reforme/",
    "6849": "/page/le-football-par-lhistoire-leconomie-et-la-morale/",
    "6872": "/page/la-grande-guerre-sest-terminee-il-y-a-cent-ans/",
    "7839": "/page/michel-serres-le-moraliste-espiegle/",
    "9106": "/page/comprendre-le-monde-entretiens-de-la-revue-xxi/",
    "9648": "/page/franz-schubert-lannee-1828/",
    "11154": "/page/la-commune-de-paris/",
    "11220": "/page/albert-camus-et-le-premier-homme/",
    "11241": "/page/beethoven-est-ne-il-y-a-250-ans/",
    "11259": "/page/leonard-bernstein-1918-1990/",
    "11369": "/page/nos-mythologies-economiques-par-eloi-laurent/",
    "11919": "/page/1979-lannee-du-grand-retournement/",
    "12725": "/page/lhasa-de-sela/",
    "12901": "/page/homo-deus-de-yuval-noah-harari/",
    "12969": "/page/les-gateaux-de-noel-alsaciens/",
    "14322": "/post/2023-02-27/",
}


def public_route_exists(public_root: Path, route: str) -> bool:
    path = route.split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"

    if path.endswith("/"):
        candidates = [public_root / path.lstrip("/") / "index.html"]
    else:
        stripped = path.lstrip("/")
        candidates = [
            public_root / stripped,
            public_root / stripped / "index.html",
            public_root / f"{stripped}.html",
        ]
    return any(candidate.exists() for candidate in candidates)


def build_attachment_routes(root: Path) -> dict[str, str]:
    routes: dict[str, str] = {}
    for path in iter_source_files(root):
        text = path.read_text(encoding="utf-8")
        for img_match in IMG_TAG_RE.finditer(text):
            attrs = {match.group("name").lower(): html.unescape(match.group("value")) for match in ATTR_RE.finditer(img_match.group(0))}
            attachment_id = attrs.get("data-id")
            full_url = attrs.get("data-full-url") or attrs.get("src")
            if attachment_id and attachment_id.isdigit() and full_url and full_url.startswith("/"):
                routes[attachment_id] = full_url
    return routes


def legacy_query_route(public_root: Path, query: str, attachment_routes: dict[str, str]) -> str | None:
    params = parse_qs(query, keep_blank_values=True)
    if "p" in params:
        legacy_id = clean_legacy_id(params["p"][0])
        if legacy_id.isdigit():
            for prefix in ("post", "page"):
                route = f"/{prefix}/{legacy_id}/"
                if public_route_exists(public_root, route):
                    return route
    if "page_id" in params:
        legacy_id = clean_legacy_id(params["page_id"][0])
        route = LEGACY_PAGE_ROUTES.get(legacy_id)
        if route and public_route_exists(public_root, route):
            return route
        if legacy_id.isdigit():
            for prefix in ("post", "page"):
                route = f"/{prefix}/{legacy_id}/"
                if public_route_exists(public_root, route):
                    return route
    if "attachment_id" in params:
        route = attachment_routes.get(params["attachment_id"][0])
        if route and public_route_exists(public_root, route):
            return route
    if "m" in params and params["m"][0].isdigit():
        return "/post/"
    if "s" in params:
        return "/post/"
    return None


def clean_legacy_id(value: str) -> str:
    match = re.search(r"\d+", value)
    return match.group(0) if match else ""


def split_entity_suffix(url: str) -> tuple[str, str]:
    cut_at = len(url)
    for suffix in HTML_ENTITY_SUFFIXES:
        index = url.find(suffix)
        if index != -1:
            cut_at = min(cut_at, index)
    return url[:cut_at], url[cut_at:]


def relativize_url(url: str, public_root: Path, attachment_routes: dict[str, str], unresolved: set[str]) -> str:
    url, suffix = split_entity_suffix(url)
    decoded = html.unescape(url)
    parts = urlsplit(decoded)
    if parts.netloc not in INTERNAL_HOSTS:
        return url + suffix

    if parts.path in ("", "/") and parts.query:
        legacy_route = legacy_query_route(public_root, parts.query, attachment_routes)
        if legacy_route:
            return legacy_route + (f"#{parts.fragment}" if parts.fragment else "") + suffix
        unresolved.add(url)
        return f"/?{parts.query}" + (f"#{parts.fragment}" if parts.fragment else "") + suffix

    route = parts.path or "/"
    if parts.query:
        route = f"{route}?{parts.query}"
    if parts.fragment:
        route = f"{route}#{parts.fragment}"
    return route + suffix


def process_file(path: Path, public_root: Path, attachment_routes: dict[str, str], dry_run: bool) -> tuple[bool, int, set[str]]:
    original = path.read_text(encoding="utf-8")
    unresolved: set[str] = set()
    rewrites = 0

    def replace_malformed_p_attr(match: re.Match[str]) -> str:
        nonlocal rewrites
        route = f"/post/{match.group('id')}/"
        if not public_route_exists(public_root, route):
            unresolved.add(match.group(0))
            return match.group(0)
        rewrites += 1
        return f"{match.group('prefix')}{route}{match.group('quote')}"

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        url = match.group(0)
        replacement = relativize_url(url, public_root, attachment_routes, unresolved)
        if replacement != url:
            rewrites += 1
        return replacement

    fixed = MALFORMED_LEGACY_P_ATTR_RE.sub(replace_malformed_p_attr, original)
    fixed = ABSOLUTE_INTERNAL_RE.sub(replace, fixed)
    changed = fixed != original
    if changed and not dry_run:
        path.write_text(fixed, encoding="utf-8")
    return changed, rewrites, unresolved


def iter_source_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in ("content", "layouts", "themes/motdujour/layouts"):
        directory = root / base
        if directory.exists():
            for suffix in ("*.md", "*.html"):
                candidates.extend(directory.rglob(suffix))
    return sorted(set(candidates))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()

    root = args.root.resolve()
    public_root = root / "public"
    if not public_root.exists():
        raise SystemExit("public/ does not exist. Run `hugo` first so legacy aliases can be resolved.")

    changed_files: list[Path] = []
    unresolved_by_file: dict[Path, set[str]] = {}
    total_rewrites = 0
    attachment_routes = build_attachment_routes(root)

    for path in iter_source_files(root):
        changed, rewrites, unresolved = process_file(path, public_root, attachment_routes, args.dry_run)
        total_rewrites += rewrites
        if changed:
            changed_files.append(path)
        if unresolved:
            unresolved_by_file[path] = unresolved

    mode = "Would update" if args.dry_run else "Updated"
    print(f"{mode} {len(changed_files)} source files")
    print(f"rewrites: {total_rewrites}")
    for path in changed_files:
        print(path.relative_to(root))

    if unresolved_by_file:
        print("unresolved legacy query URLs:")
        for path, urls in sorted(unresolved_by_file.items()):
            print(f"{path.relative_to(root)}: {', '.join(sorted(urls))}")

    return 1 if unresolved_by_file else 0


if __name__ == "__main__":
    raise SystemExit(main())
