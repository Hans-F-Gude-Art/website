#!/usr/bin/env python3
"""Fix gallery data files to use actual artwork slugs.

The artwork files have truncated filenames that don't match the image filenames.
This script builds a mapping from image paths to artwork slugs, then updates
the gallery data files to use the correct slugs.
"""

import re
import sys
from pathlib import Path


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown file."""
    if not content.startswith('---'):
        return {}

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}

    frontmatter = {}
    for line in parts[1].strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            frontmatter[key] = value

    return frontmatter


def build_image_to_slug_map(artworks_dir: Path) -> dict[str, str]:
    """Build mapping from image basename (without ext) to artwork slug."""
    mapping = {}

    for filepath in artworks_dir.glob('*.md'):
        content = filepath.read_text()
        frontmatter = extract_frontmatter(content)

        if 'image' in frontmatter:
            # Get image basename without extension
            image_path = frontmatter['image']
            image_basename = Path(image_path).stem  # filename without extension

            # Artwork slug is the md filename without extension
            artwork_slug = filepath.stem

            mapping[image_basename] = artwork_slug

    return mapping


def fix_gallery_file(filepath: Path, image_to_slug: dict[str, str], dry_run: bool = False) -> tuple[int, int]:
    """Fix slugs in a gallery data file. Returns (fixed_count, missing_count)."""
    content = filepath.read_text()
    lines = content.strip().split('\n')

    new_lines = []
    fixed = 0
    missing = 0

    for line in lines:
        if line.startswith('- '):
            old_slug = line[2:].strip()

            if old_slug in image_to_slug:
                new_slug = image_to_slug[old_slug]
                if new_slug != old_slug:
                    new_lines.append(f"- {new_slug}")
                    fixed += 1
                else:
                    new_lines.append(line)
            else:
                # Slug not found in mapping - might already be correct or truly missing
                new_lines.append(line)
                missing += 1
        else:
            new_lines.append(line)

    if not dry_run and fixed > 0:
        filepath.write_text('\n'.join(new_lines) + '\n')

    return fixed, missing


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would be fixed without making changes")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    galleries_dir = project_root / '_data' / 'galleries'
    artworks_dir = project_root / '_artworks'

    print("Building image-to-slug mapping from artwork files...")
    image_to_slug = build_image_to_slug_map(artworks_dir)
    print(f"Found {len(image_to_slug)} artwork image mappings\n")

    if args.dry_run:
        print("(dry run - no changes will be made)\n")

    total_fixed = 0
    total_missing = 0

    for filepath in sorted(galleries_dir.glob('*.yml')):
        fixed, missing = fix_gallery_file(filepath, image_to_slug, dry_run=args.dry_run)
        if fixed > 0 or missing > 0:
            status = "would fix" if args.dry_run else "fixed"
            print(f"  {filepath.name}: {status} {fixed} slugs, {missing} not in mapping")
        total_fixed += fixed
        total_missing += missing

    print(f"\nTotal: {total_fixed} slugs fixed, {total_missing} not found in artwork mapping")

    if total_missing > 0:
        print("\nNote: 'not in mapping' means the slug wasn't found as an image basename")
        print("in any artwork file. These may be artwork files that don't exist yet.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
