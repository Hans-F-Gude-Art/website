#!/usr/bin/env python3
"""Apply medium proposals from the review swarm to artwork frontmatter.

Reads _reports/medium_review/proposals/*.yml, each a list of entries:

    - slug: some-artwork
      mediums: [pencil]
      confidence: high        # high | medium | low
      notes: optional free text

Applies entries at or above the confidence threshold (default: high) to
artworks that still lack a mediums block; prints the rest for human review.

Usage:
    uv run --with pyyaml python3 _scripts/apply_medium_proposals.py [--threshold medium] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
PROPOSALS = ROOT / "_reports" / "medium_review" / "proposals"
VALID = {"oil", "watercolor", "gouache", "charcoal", "pencil", "pen-ink",
         "digital", "photograph"}
LEVELS = {"low": 0, "medium": 1, "high": 2}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", default="high", choices=LEVELS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    applied, skipped, errors = 0, [], []
    for f in sorted(PROPOSALS.glob("*.yml")):
        for e in yaml.safe_load(f.read_text()) or []:
            slug, mediums = e.get("slug"), e.get("mediums") or []
            conf = e.get("confidence", "low")
            path = ROOT / "_artworks" / f"{slug}.md"
            if not path.exists():
                errors.append(f"{f.name}: no artwork '{slug}'")
                continue
            bad = set(mediums) - VALID
            if bad or not mediums:
                errors.append(f"{slug}: invalid mediums {mediums}")
                continue
            text = path.read_text()
            if "\nmediums:\n" in text:
                errors.append(f"{slug}: already tagged, skipping")
                continue
            if LEVELS[conf] < LEVELS[args.threshold]:
                skipped.append(f"{slug}: {mediums} ({conf}) {e.get('notes', '')}")
                continue
            if not args.dry_run:
                lines = text.split("\n")
                end = next(i for i in range(1, len(lines))
                           if lines[i].strip() == "---")
                lines[end:end] = ["mediums:"] + [f"  - {m}" for m in mediums]
                path.write_text("\n".join(lines))
            applied += 1

    print(f"applied: {applied}{' (dry run)' if args.dry_run else ''}")
    if skipped:
        print(f"\nbelow threshold ({len(skipped)}) - review by hand:")
        print("\n".join(f"  {s}" for s in skipped))
    if errors:
        print(f"\nerrors ({len(errors)}):")
        print("\n".join(f"  {e}" for e in errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
