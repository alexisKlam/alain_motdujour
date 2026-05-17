#!/usr/bin/env python3
"""Fix malformed article links that Hugo renders as dead local URLs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REPLACEMENTS = {
    "%3chttp://www.rtbf.be/info/monde/detail_chypre-les-deux-parties-de-l-ile-grecque-et-turque-vont-se-reparler?id=8197721%20%3e": "http://www.rtbf.be/info/monde/detail_chypre-les-deux-parties-de-l-ile-grecque-et-turque-vont-se-reparler?id=8197721",
    'href="lemotdujour.fr/?p=8036"': 'href="/post/8036/"',
    'href="%22OK,%20Boomer%22%20:%20les%2055/75%20ans,%20à%20leur%20tour%20victime%20d\'une%20révolte%20générationnelle"': 'href="https://www.mediatheques.strasbourg.eu/doc/RADIOFRANCE/2019C26359S0336/ok-boomer-les-55-75-ans-a-leur-tour-victime-d-une-revolte-generationnelle"',
    'href="La%20part%20d’ange%20en%20nous.%20Histoire%20de%20la%20violence%20et%20de%20son%20déclin"': 'href="/post/2017-11-21/"',
    'href="%5b…%5d"': 'href="https://www.revue-farouest.fr/feuilletons/les-raisins-de-la-misere/"',
    'href="Alexeï%20Navalny,%20de%20l’engagement%20au%20sacrifice"': 'href="https://www.prison-insider.com/articles/russie-alexei-navalny-de-l-engagement-au-sacrifice"',
    "'Maintien de l&#039;ordre'": "\"Maintien de l'ordre\"",
}

REGEX_REPLACEMENTS = [
    (
        re.compile(r'href="\u200bhttps:/([^"]*?)\u200b"'),
        r'href="https://\1"',
    ),
    (
        re.compile(r'href="S\'exprimant[^"]*Ebola[^"]*"'),
        'href="https://www.europe1.fr/international/nous-ne-sommes-pas-prets-quand-bill-gates-predisait-presque-lepidemie-de-coronavirus-3956514"',
    ),
]


def process_file(path: Path, dry_run: bool) -> tuple[bool, int]:
    original = path.read_text(encoding="utf-8")
    fixed = original
    rewrites = 0

    for old, new in REPLACEMENTS.items():
        count = fixed.count(old)
        if count:
            rewrites += count
            fixed = fixed.replace(old, new)

    for pattern, replacement in REGEX_REPLACEMENTS:
        fixed, count = pattern.subn(replacement, fixed)
        rewrites += count

    changed = fixed != original
    if changed and not dry_run:
        path.write_text(fixed, encoding="utf-8")
    return changed, rewrites


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()

    root = args.root.resolve()
    paths = sorted((root / "content" / "post").glob("*.md"))
    changed_files: list[Path] = []
    total_rewrites = 0

    for path in paths:
        changed, rewrites = process_file(path, args.dry_run)
        total_rewrites += rewrites
        if changed:
            changed_files.append(path)

    mode = "Would update" if args.dry_run else "Updated"
    print(f"{mode} {len(changed_files)} article files")
    print(f"rewrites: {total_rewrites}")
    for path in changed_files:
        print(path.relative_to(root))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
