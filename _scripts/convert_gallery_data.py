#!/usr/bin/env python3
"""Convert gallery data files from image/alt format to slug-only format.

Before:
    - image: landscapes-mt-diablo/winter-storm-over-mt-diablo.jpg
      alt: "Winter Storm Over Mt. Diablo"

After:
    - winter-storm-over-mt-diablo
"""

import os
import re
from pathlib import Path


def extract_slug_from_image(image_path: str) -> str:
    """Extract slug from image path (basename without extension)."""
    basename = os.path.basename(image_path)
    slug = os.path.splitext(basename)[0]
    return slug


def parse_gallery_yaml(content: str) -> list[dict]:
    """Parse the old-format gallery YAML (simple parser, no pyyaml dependency)."""
    entries = []
    current_entry = {}

    for line in content.split('\n'):
        if line.startswith('- image:'):
            if current_entry:
                entries.append(current_entry)
            image_value = line.split('- image:', 1)[1].strip()
            current_entry = {'image': image_value}
        elif line.strip().startswith('alt:'):
            alt_value = line.split('alt:', 1)[1].strip().strip('"\'')
            current_entry['alt'] = alt_value

    if current_entry:
        entries.append(current_entry)

    return entries


def convert_to_slug_format(entries: list[dict]) -> str:
    """Convert entries to slug-only YAML format."""
    lines = []
    for entry in entries:
        if 'image' in entry:
            slug = extract_slug_from_image(entry['image'])
            lines.append(f"- {slug}")
    return '\n'.join(lines) + '\n'


def process_gallery_file(filepath: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Process a single gallery file. Returns (count, issues)."""
    content = filepath.read_text()

    # Skip if already in slug-only format (lines are just "- slug")
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
    if lines and all(re.match(r'^- [\w-]+$', l) for l in lines):
        print(f"  {filepath.name}: already converted, skipping")
        return 0, []

    entries = parse_gallery_yaml(content)
    if not entries:
        print(f"  {filepath.name}: no entries found, skipping")
        return 0, []

    new_content = convert_to_slug_format(entries)

    if dry_run:
        print(f"  {filepath.name}: would convert {len(entries)} entries")
    else:
        filepath.write_text(new_content)
        print(f"  {filepath.name}: converted {len(entries)} entries")

    return len(entries), []


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would be converted without making changes")
    args = parser.parse_args()

    galleries_dir = Path(__file__).parent.parent / '_data' / 'galleries'

    if not galleries_dir.exists():
        print(f"Error: {galleries_dir} does not exist")
        return 1

    print(f"Converting gallery data files in {galleries_dir}")
    if args.dry_run:
        print("(dry run - no changes will be made)\n")

    total = 0
    for filepath in sorted(galleries_dir.glob('*.yml')):
        count, _ = process_gallery_file(filepath, dry_run=args.dry_run)
        total += count

    print(f"\nTotal entries processed: {total}")
    return 0


if __name__ == '__main__':
    exit(main())
