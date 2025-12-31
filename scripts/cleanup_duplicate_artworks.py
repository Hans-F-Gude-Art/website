#!/usr/bin/env python3
"""Find and remove duplicate artwork files that reference the same image."""

import re
from collections import defaultdict
from pathlib import Path


def extract_image_path(md_file: Path) -> str | None:
    """Extract the image path from an artwork markdown file."""
    content = md_file.read_text()
    match = re.search(r'^image:\s*["\']?([^"\']+)["\']?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def find_duplicate_artworks(artworks_dir: Path) -> dict[str, list[Path]]:
    """Find artwork files that reference the same image.

    Returns dict mapping image_path -> list of md files referencing it.
    Only includes images with more than one referencing file.
    """
    image_to_files: dict[str, list[Path]] = defaultdict(list)

    for md_file in artworks_dir.glob("*.md"):
        image_path = extract_image_path(md_file)
        if image_path:
            image_to_files[image_path].append(md_file)

    # Filter to only duplicates
    return {img: files for img, files in image_to_files.items() if len(files) > 1}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean up duplicate artwork files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    artworks_dir = base_dir / "_artworks"

    duplicates = find_duplicate_artworks(artworks_dir)

    if not duplicates:
        print("No duplicate artwork files found!")
        return 0

    print(f"Found {len(duplicates)} images with duplicate artwork files:\n")

    files_to_delete = []

    for image_path, md_files in sorted(duplicates.items()):
        print(f"Image: {image_path}")
        # Keep the first file (alphabetically), delete the rest
        md_files_sorted = sorted(md_files, key=lambda p: p.name)
        keep = md_files_sorted[0]
        delete = md_files_sorted[1:]

        print(f"  KEEP: {keep.name}")
        for f in delete:
            print(f"  DELETE: {f.name}")
            files_to_delete.append(f)
        print()

    print(f"\nTotal files to delete: {len(files_to_delete)}")

    if not args.dry_run and files_to_delete:
        print("\nDeleting files...")
        for f in files_to_delete:
            f.unlink()
            print(f"  Deleted: {f.name}")
        print("Done!")
    elif args.dry_run:
        print("\nDry run - no files deleted. Run without --dry-run to delete.")

    return 0


if __name__ == "__main__":
    exit(main())
