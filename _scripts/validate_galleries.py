#!/usr/bin/env python3
"""Validate gallery data files against artwork collection.

Checks:
- ERROR: Duplicate slugs within a gallery data file
- ERROR: Slugs in data file with no matching artwork
- ERROR: Artwork not tagged for the gallery it appears in (--check-tags)
- WARNING: Artwork files not referenced by any gallery (--warn-orphans)

Exit codes:
- 0: All checks passed (warnings are OK)
- 1: Errors found

Usage:
    python3 _scripts/validate_galleries.py [--warn-orphans] [--check-tags]
"""

import re
import sys
from pathlib import Path


def parse_slug_list(content: str) -> list[str]:
    """Parse a YAML file containing a simple list of slugs."""
    slugs = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            slug = line[2:].strip()
            if slug:
                slugs.append(slug)
    return slugs


def get_artwork_slugs(artworks_dir: Path) -> set[str]:
    """Get all artwork slugs from the _artworks directory."""
    slugs = set()
    for filepath in artworks_dir.glob('*.md'):
        slug = filepath.stem  # filename without .md
        slugs.add(slug)
    return slugs


def get_artwork_galleries(artworks_dir: Path) -> dict[str, list[str]]:
    """Get mapping of artwork slug to list of galleries it belongs to."""
    artwork_galleries = {}
    for filepath in artworks_dir.glob('*.md'):
        slug = filepath.stem
        content = filepath.read_text()

        # Parse galleries from frontmatter
        galleries = []
        in_galleries = False
        for line in content.split('\n'):
            if line.strip() == 'galleries:':
                in_galleries = True
            elif in_galleries:
                if line.startswith('  - '):
                    galleries.append(line.strip()[2:].strip())
                elif line.startswith('---') or (line and not line.startswith(' ')):
                    break

        artwork_galleries[slug] = galleries

    return artwork_galleries


def validate_gallery(filepath: Path, artwork_slugs: set[str],
                     artwork_galleries: dict[str, list[str]] | None = None,
                     check_tags: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Validate a single gallery data file.

    Returns: (errors, warnings, slugs_used)
    """
    errors = []
    warnings = []
    slugs_used = []

    content = filepath.read_text()
    slugs = parse_slug_list(content)

    # Derive gallery_id from filename (e.g., cal_rowing.yml -> cal-rowing)
    gallery_id = filepath.stem.replace('_', '-')

    # Check for duplicates
    seen = {}
    for i, slug in enumerate(slugs, 1):
        if slug in seen:
            errors.append(f"{filepath.name}:{i}: duplicate slug '{slug}' (first at line {seen[slug]})")
        else:
            seen[slug] = i
            slugs_used.append(slug)

        # Check if artwork exists
        if slug not in artwork_slugs:
            errors.append(f"{filepath.name}:{i}: no artwork file for slug '{slug}'")
        elif check_tags and artwork_galleries:
            # Check if artwork is tagged for this gallery
            artwork_tags = artwork_galleries.get(slug, [])
            if gallery_id not in artwork_tags:
                errors.append(f"{filepath.name}:{i}: artwork '{slug}' not tagged for gallery '{gallery_id}' (tagged: {artwork_tags})")

    return errors, warnings, slugs_used


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--warn-orphans', action='store_true',
                        help="Warn about artworks not in any gallery")
    parser.add_argument('--error-orphans', action='store_true',
                        help="Treat orphaned artworks as errors (implies --warn-orphans)")
    parser.add_argument('--check-tags', action='store_true',
                        help="Check that artworks are tagged for the galleries they appear in")
    args = parser.parse_args()

    # Find project root (where _data and _artworks are)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    galleries_dir = project_root / '_data' / 'galleries'
    artworks_dir = project_root / '_artworks'

    if not galleries_dir.exists():
        print(f"ERROR: {galleries_dir} does not exist")
        return 1

    if not artworks_dir.exists():
        print(f"ERROR: {artworks_dir} does not exist")
        return 1

    # Get all valid artwork slugs
    artwork_slugs = get_artwork_slugs(artworks_dir)
    print(f"Found {len(artwork_slugs)} artwork files")

    # Get artwork gallery tags if needed
    artwork_galleries = None
    if args.check_tags:
        artwork_galleries = get_artwork_galleries(artworks_dir)

    # Validate each gallery
    all_errors = []
    all_warnings = []
    all_slugs_used = set()

    gallery_files = sorted(galleries_dir.glob('*.yml'))
    print(f"Validating {len(gallery_files)} gallery data files...\n")

    for filepath in gallery_files:
        errors, warnings, slugs_used = validate_gallery(
            filepath, artwork_slugs, artwork_galleries, check_tags=args.check_tags
        )
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        all_slugs_used.update(slugs_used)

    # Check for orphaned artworks
    if args.warn_orphans or args.error_orphans:
        orphans = artwork_slugs - all_slugs_used
        for slug in sorted(orphans):
            msg = f"_artworks/{slug}.md: not referenced by any gallery"
            if args.error_orphans:
                all_errors.append(msg)
            else:
                all_warnings.append(msg)

    # Report results
    if all_errors:
        print("ERRORS:")
        for error in all_errors:
            print(f"  {error}")
        print()

    if all_warnings:
        print("WARNINGS:")
        for warning in all_warnings:
            print(f"  {warning}")
        print()

    # Summary
    error_count = len(all_errors)
    warning_count = len(all_warnings)

    if error_count == 0 and warning_count == 0:
        print("All checks passed.")
        return 0
    elif error_count == 0:
        print(f"Passed with {warning_count} warning(s).")
        return 0
    else:
        print(f"FAILED: {error_count} error(s), {warning_count} warning(s).")
        return 1


if __name__ == '__main__':
    sys.exit(main())
