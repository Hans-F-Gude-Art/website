#!/usr/bin/env python3
"""Migrate artwork image paths from relative to absolute.

Changes:
    image: landscapes-mt-diablo/mt-diablo-at-sunset.jpg
To:
    image: /assets/images/galleries/landscapes-mt-diablo/mt-diablo-at-sunset.jpg
"""

import re
from pathlib import Path

ARTWORKS_DIR = Path(__file__).parent.parent / "_artworks"
GALLERIES_PREFIX = "/assets/images/galleries/"


def migrate_file(filepath: Path) -> bool:
    """Migrate a single artwork file. Returns True if modified."""
    content = filepath.read_text()

    # Match image: followed by a path that doesn't start with /
    pattern = r'^(image:\s*)([^/\s].*)$'

    def replace_path(match):
        prefix = match.group(1)
        path = match.group(2)
        return f"{prefix}{GALLERIES_PREFIX}{path}"

    new_content, count = re.subn(pattern, replace_path, content, flags=re.MULTILINE)

    if count > 0:
        filepath.write_text(new_content)
        return True
    return False


def main():
    if not ARTWORKS_DIR.exists():
        print(f"Error: {ARTWORKS_DIR} not found")
        return 1

    modified = 0
    skipped = 0

    for filepath in sorted(ARTWORKS_DIR.glob("*.md")):
        if migrate_file(filepath):
            print(f"Migrated: {filepath.name}")
            modified += 1
        else:
            skipped += 1

    print(f"\nDone: {modified} files migrated, {skipped} already absolute or no image field")
    return 0


if __name__ == "__main__":
    exit(main())
