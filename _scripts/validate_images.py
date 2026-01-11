#!/usr/bin/env python3
"""
Validate image references in artwork files and data files.

Checks that all images referenced actually exist on disk.

Usage:
    uv run python3 _scripts/validate_images.py
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ARTWORKS_DIR = PROJECT_ROOT / "_artworks"
DATA_DIR = PROJECT_ROOT / "_data"


def extract_image_path(content: str) -> str | None:
    """Extract image path from frontmatter."""
    match = re.search(r'^image:\s*["\']?([^"\'\n]+)["\']?\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def check_path(image_path: str, source_file: str, errors: list) -> bool:
    """Check if an image path exists. Returns True if valid."""
    if not image_path or not image_path.startswith("/assets"):
        return True  # Skip non-asset paths

    fs_path = PROJECT_ROOT / image_path.lstrip("/")

    if not fs_path.exists():
        # Try to find similar files
        parent = fs_path.parent
        similar = []
        if parent.exists():
            for f in parent.iterdir():
                if fs_path.stem in f.stem or f.stem in fs_path.stem:
                    similar.append(f.name)

        errors.append({
            "file": source_file,
            "image": image_path,
            "similar": similar,
        })
        return False
    return True


def main():
    errors = []
    artwork_count = 0
    data_count = 0

    # Check artwork files
    for md_file in sorted(ARTWORKS_DIR.glob("*.md")):
        content = md_file.read_text()
        image_path = extract_image_path(content)
        if image_path:
            artwork_count += 1
            check_path(image_path, f"_artworks/{md_file.name}", errors)

    # Check data files for image references
    for yml_file in sorted(DATA_DIR.glob("*.yml")):
        content = yml_file.read_text()
        for match in re.finditer(r'image:\s*([^\n]+)', content):
            image_path = match.group(1).strip()
            data_count += 1
            check_path(image_path, f"_data/{yml_file.name}", errors)

    # Check hub gallery files
    for yml_file in sorted(DATA_DIR.glob("*_galleries.yml")):
        content = yml_file.read_text()
        for match in re.finditer(r'image:\s*([^\n]+)', content):
            image_path = match.group(1).strip()
            data_count += 1
            check_path(image_path, f"_data/{yml_file.name}", errors)

    print(f"Checked {artwork_count} artwork files and {data_count} data file references\n")

    if errors:
        print(f"=== MISSING IMAGES ({len(errors)}) ===\n")
        for err in errors:
            print(f"{err['file']}:")
            print(f"  References: {err['image']}")
            if err['similar']:
                print(f"  Similar files: {', '.join(err['similar'])}")
            else:
                print(f"  No similar files found")
            print()
    else:
        print("All image references are valid!")

    return len(errors)


if __name__ == "__main__":
    exit(main())
