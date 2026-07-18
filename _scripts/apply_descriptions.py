#!/usr/bin/env python3
"""Apply descriptions from archive_reconciliation.yml to _artworks/*.md.

Reads _reports/archive_reconciliation.yml and, for each entry in
add_description, inserts `description: "..."` into the frontmatter of
the corresponding artwork file.  Skips files that already have a
description.

Usage:
    uv run --with pyyaml python3 _scripts/apply_descriptions.py [--dry-run]
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Run with: uv run --with pyyaml python3 ...")
    sys.exit(1)

ARTWORKS_DIR = Path("_artworks")
RECONCILIATION_FILE = Path("_reports/archive_reconciliation.yml")


def load_descriptions() -> dict[str, str]:
    """Parse add_description section of the reconciliation file."""
    with open(RECONCILIATION_FILE, encoding="utf-8") as f:
        content = f.read()

    # Grab the add_description block
    m = re.search(r"^add_description:\n(.*?)(?=^\w|\Z)", content, re.DOTALL | re.MULTILINE)
    if not m:
        return {}

    block = m.group(1)
    result: dict[str, str] = {}
    current_slug: str | None = None

    for line in block.splitlines():
        # Slug line: "  slug:"
        slug_m = re.match(r"^  ([a-z0-9][a-z0-9-]+):", line)
        if slug_m:
            current_slug = slug_m.group(1)
            continue
        # Description line: "    description: ..."
        if current_slug:
            desc_m = re.match(r'    description: (.+)', line)
            if desc_m:
                raw = desc_m.group(1)
                # Strip surrounding double-quotes if present
                if raw.startswith('"') and raw.endswith('"'):
                    raw = raw[1:-1]
                # Unescape internal escaped quotes
                raw = raw.replace('\\"', '"')
                result[current_slug] = raw.strip()

    return result


def insert_description(content: str, description: str) -> str | None:
    """Insert description: into YAML frontmatter after title:.

    Returns new content, or None if no insertion point found.
    """
    # Find frontmatter boundaries
    fm_m = re.match(r"^(---\s*\n)(.*?)(\n---)", content, re.DOTALL)
    if not fm_m:
        return None

    preamble = fm_m.group(1)
    fm_body = fm_m.group(2)
    closing = fm_m.group(3)
    rest = content[fm_m.end():]

    # Check if description already exists
    if re.search(r"^description:", fm_body, re.MULTILINE):
        return None

    # Insert after title: line
    def add_after_title(m: re.Match) -> str:
        # Escape any double-quotes in description for YAML
        esc = description.replace('"', '\\"')
        return m.group(0) + f'\ndescription: "{esc}"'

    new_fm, n = re.subn(r'^title:.*', add_after_title, fm_body, count=1, flags=re.MULTILINE)
    if n == 0:
        # No title line; append before closing
        new_fm = fm_body + f'\ndescription: "{description.replace(chr(34), chr(92)+chr(34))}"'

    return preamble + new_fm + closing + rest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    descriptions = load_descriptions()
    print(f"Loaded {len(descriptions)} descriptions to apply")

    applied = 0
    skipped_exists = 0
    skipped_missing = 0

    for slug, description in sorted(descriptions.items()):
        artwork_path = ARTWORKS_DIR / f"{slug}.md"
        if not artwork_path.exists():
            print(f"  MISSING: {slug}.md", file=sys.stderr)
            skipped_missing += 1
            continue

        original = artwork_path.read_text(encoding="utf-8")
        new_content = insert_description(original, description)
        if new_content is None:
            skipped_exists += 1
            continue

        if args.dry_run:
            print(f"  Would add to {slug}: {description[:60]!r}")
        else:
            artwork_path.write_text(new_content, encoding="utf-8")
            applied += 1

    verb = "Would add" if args.dry_run else "Added"
    print(f"\n{verb} descriptions: {applied}")
    print(f"Skipped (already have description): {skipped_exists}")
    print(f"Skipped (artwork file missing): {skipped_missing}")


if __name__ == "__main__":
    main()
