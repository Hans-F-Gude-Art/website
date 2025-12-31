#!/usr/bin/env python3
"""Find duplicate images in the galleries folder by content hash."""

import hashlib
from collections import defaultdict
from pathlib import Path


def hash_file(filepath: Path, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of a file, reading in chunks for efficiency."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def find_duplicates(galleries_dir: Path) -> dict[str, list[Path]]:
    """Find all duplicate images by content hash.

    Returns a dict mapping hash -> list of file paths with that hash.
    Only includes hashes with more than one file (actual duplicates).
    """
    hash_to_files: dict[str, list[Path]] = defaultdict(list)

    # Scan all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    for filepath in galleries_dir.rglob("*"):
        if filepath.is_file() and filepath.suffix.lower() in image_extensions:
            file_hash = hash_file(filepath)
            hash_to_files[file_hash].append(filepath)

    # Filter to only duplicates (more than one file with same hash)
    return {h: files for h, files in hash_to_files.items() if len(files) > 1}


def write_report(duplicates: dict[str, list[Path]], output_path: Path, base_dir: Path) -> None:
    """Write duplicate report as YAML."""
    # Calculate stats
    total_sets = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())  # -1 because one is the "original"
    space_wasted = sum(
        files[0].stat().st_size * (len(files) - 1)
        for files in duplicates.values()
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(f"# Duplicate Image Report\n")
        f.write(f"# Duplicate sets found: {total_sets}\n")
        f.write(f"# Total duplicate files: {total_duplicate_files}\n")
        f.write(f"# Potential space savings: {space_wasted / 1024 / 1024:.1f} MB\n")
        f.write(f"#\n")
        f.write(f"# Each set below contains identical images (same content, different paths)\n")
        f.write(f"\n")
        f.write(f"duplicates:\n")

        # Sort by number of duplicates (most duplicates first)
        sorted_duplicates = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)

        for file_hash, files in sorted_duplicates:
            size_bytes = files[0].stat().st_size
            f.write(f"  - hash: \"{file_hash[:16]}...\"\n")
            f.write(f"    size_bytes: {size_bytes}\n")
            f.write(f"    count: {len(files)}\n")
            f.write(f"    files:\n")
            for filepath in sorted(files):
                relative_path = filepath.relative_to(base_dir)
                f.write(f"      - {relative_path}\n")
            f.write(f"\n")


def main():
    # Paths relative to script location
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    galleries_dir = base_dir / "assets" / "images" / "galleries"
    output_path = base_dir / "reports" / "duplicate_images.yml"

    if not galleries_dir.exists():
        print(f"Error: Galleries directory not found: {galleries_dir}")
        return 1

    print(f"Scanning images in: {galleries_dir}")
    duplicates = find_duplicates(galleries_dir)

    # Print summary
    total_sets = len(duplicates)
    total_duplicate_files = sum(len(files) - 1 for files in duplicates.values())
    space_wasted = sum(
        files[0].stat().st_size * (len(files) - 1)
        for files in duplicates.values()
    )

    print(f"\nResults:")
    print(f"  Duplicate sets found: {total_sets}")
    print(f"  Total duplicate files: {total_duplicate_files}")
    print(f"  Potential space savings: {space_wasted / 1024 / 1024:.1f} MB")

    if total_sets > 0:
        write_report(duplicates, output_path, base_dir)
        print(f"\nReport written to: {output_path}")
    else:
        print("\nNo duplicates found!")

    return 0


if __name__ == "__main__":
    exit(main())
