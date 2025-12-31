#!/usr/bin/env python3
"""Apply deduplication based on annotated duplicate_images_annotated.yml."""

import os
import re
import shutil
from pathlib import Path

import yaml


def load_dedup_plan(plan_path: Path) -> list[dict]:
    """Load the annotated deduplication plan."""
    with open(plan_path) as f:
        data = yaml.safe_load(f)
    return data.get("duplicates", [])


def update_gallery_yaml_files(old_path: str, new_path: str, data_dir: Path) -> int:
    """Update references in _data/galleries/*.yml files.

    Returns count of files updated.
    """
    updated = 0
    old_ref = old_path.replace("assets/images/galleries/", "")
    new_ref = new_path.replace("assets/images/galleries/", "")

    for yml_file in data_dir.glob("*.yml"):
        content = yml_file.read_text()
        if old_ref in content:
            new_content = content.replace(old_ref, new_ref)
            yml_file.write_text(new_content)
            updated += 1
            print(f"  Updated {yml_file.name}: {old_ref} -> {new_ref}")

    return updated


def update_hub_navigation_files(old_path: str, new_path: str, data_dir: Path) -> int:
    """Update references in _data/*_galleries.yml hub navigation files.

    Returns count of files updated.
    """
    updated = 0
    old_ref = old_path.replace("assets/images/galleries/", "")
    new_ref = new_path.replace("assets/images/galleries/", "")

    for yml_file in data_dir.glob("*_galleries.yml"):
        content = yml_file.read_text()
        if old_ref in content:
            new_content = content.replace(old_ref, new_ref)
            yml_file.write_text(new_content)
            updated += 1
            print(f"  Updated hub nav {yml_file.name}: {old_ref} -> {new_ref}")

    return updated


def update_artwork_files(old_path: str, new_path: str, artworks_dir: Path) -> int:
    """Update references in _artworks/*.md files.

    Returns count of files updated.
    """
    updated = 0
    old_ref = old_path.replace("assets/images/galleries/", "")
    new_ref = new_path.replace("assets/images/galleries/", "")

    for md_file in artworks_dir.glob("*.md"):
        content = md_file.read_text()
        if old_ref in content:
            new_content = content.replace(old_ref, new_ref)
            md_file.write_text(new_content)
            updated += 1
            print(f"  Updated {md_file.name}: {old_ref} -> {new_ref}")

    return updated


def extract_artwork_frontmatter(md_file: Path) -> dict | None:
    """Extract frontmatter from an artwork markdown file."""
    content = md_file.read_text()
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None
    return None


def merge_duplicate_artworks(artworks_dir: Path, dry_run: bool = True) -> dict:
    """Find and merge artwork files that reference the same image.

    For each image referenced by multiple artwork files:
    - Keep the file with the shortest name (most canonical)
    - Merge all galleries from duplicates into the kept file
    - Delete the duplicate files

    Returns stats dict.
    """
    from collections import defaultdict

    stats = {"artworks_merged": 0, "artworks_deleted": 0}

    # Build map of image -> list of artwork files
    image_to_files: dict[str, list[Path]] = defaultdict(list)

    for md_file in artworks_dir.glob("*.md"):
        fm = extract_artwork_frontmatter(md_file)
        if fm and "image" in fm:
            image_to_files[fm["image"]].append(md_file)

    # Process duplicates
    for image_path, md_files in image_to_files.items():
        if len(md_files) <= 1:
            continue

        # Sort by filename length (prefer shorter, more canonical names)
        md_files_sorted = sorted(md_files, key=lambda p: (len(p.stem), p.name))
        keep_file = md_files_sorted[0]
        delete_files = md_files_sorted[1:]

        # Collect all galleries from all files
        all_galleries = set()
        keep_title = None
        for md_file in md_files:
            fm = extract_artwork_frontmatter(md_file)
            if fm:
                if md_file == keep_file:
                    keep_title = fm.get("title", "")
                galleries = fm.get("galleries", [])
                if isinstance(galleries, list):
                    all_galleries.update(galleries)

        print(f"\n  Image: {image_path}")
        print(f"    KEEP: {keep_file.name}")
        for df in delete_files:
            print(f"    DELETE: {df.name}")
        print(f"    Merged galleries: {sorted(all_galleries)}")

        if not dry_run:
            # Rewrite the kept file with merged galleries
            galleries_yaml = "\n".join(f"  - {g}" for g in sorted(all_galleries))
            new_content = f'''---
layout: artwork
title: "{keep_title}"
image: {image_path}
galleries:
{galleries_yaml}
---
'''
            keep_file.write_text(new_content)

            # Delete duplicates
            for df in delete_files:
                df.unlink()
                stats["artworks_deleted"] += 1

        stats["artworks_merged"] += 1

    return stats


def process_duplicate_set(
    dup: dict,
    base_dir: Path,
    dry_run: bool = True
) -> dict:
    """Process a single duplicate set.

    Returns stats dict with counts.
    """
    stats = {"files_deleted": 0, "files_renamed": 0, "refs_updated": 0}

    file_to_keep = dup.get("file_to_keep")
    new_file_name = dup.get("new_file_name")
    all_files = dup.get("files", [])

    if not file_to_keep or not new_file_name:
        print(f"  SKIP: Missing file_to_keep or new_file_name for hash {dup.get('hash')}")
        return stats

    keep_path = base_dir / file_to_keep
    if not keep_path.exists():
        print(f"  ERROR: file_to_keep does not exist: {file_to_keep}")
        return stats

    # Determine the canonical path (same gallery, but with new filename)
    gallery_dir = keep_path.parent
    canonical_path = gallery_dir / new_file_name
    canonical_rel = str(canonical_path.relative_to(base_dir))

    data_dir = base_dir / "_data" / "galleries"
    hub_data_dir = base_dir / "_data"
    artworks_dir = base_dir / "_artworks"

    # Step 1: Rename the kept file if needed
    if keep_path != canonical_path:
        print(f"  Rename: {keep_path.name} -> {new_file_name}")
        if not dry_run:
            keep_path.rename(canonical_path)
        stats["files_renamed"] += 1

        # Update references from old kept path to new canonical path
        old_rel = file_to_keep
        new_rel = canonical_rel
        if not dry_run:
            update_gallery_yaml_files(old_rel, new_rel, data_dir)
            update_hub_navigation_files(old_rel, new_rel, hub_data_dir)
            update_artwork_files(old_rel, new_rel, artworks_dir)
        stats["refs_updated"] += 1

    # Step 2: Update references from all duplicate paths to canonical path
    for dup_file in all_files:
        if dup_file == file_to_keep:
            continue  # Already handled above

        dup_path = base_dir / dup_file

        # Update references before deleting
        if not dry_run:
            refs_gallery = update_gallery_yaml_files(dup_file, canonical_rel, data_dir)
            refs_hub = update_hub_navigation_files(dup_file, canonical_rel, hub_data_dir)
            refs_artwork = update_artwork_files(dup_file, canonical_rel, artworks_dir)
            stats["refs_updated"] += refs_gallery + refs_hub + refs_artwork

        # Delete the duplicate
        if dup_path.exists():
            print(f"  Delete: {dup_file}")
            if not dry_run:
                dup_path.unlink()
            stats["files_deleted"] += 1
        else:
            print(f"  SKIP (not found): {dup_file}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apply image deduplication")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("_reports/duplicate_images_annotated.yml"),
        help="Path to annotated dedup plan"
    )
    args = parser.parse_args()

    # Paths relative to script location
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    plan_path = base_dir / args.plan

    if not plan_path.exists():
        print(f"Error: Plan file not found: {plan_path}")
        return 1

    print(f"Loading plan from: {plan_path}")
    duplicates = load_dedup_plan(plan_path)
    print(f"Found {len(duplicates)} duplicate sets to process")

    if args.dry_run:
        print("\n=== DRY RUN MODE - No changes will be made ===\n")

    total_stats = {"files_deleted": 0, "files_renamed": 0, "refs_updated": 0}

    for i, dup in enumerate(duplicates, 1):
        hash_short = dup.get("hash", "unknown")[:16]
        count = dup.get("count", 0)
        print(f"\n[{i}/{len(duplicates)}] Processing {hash_short}... ({count} files)")

        stats = process_duplicate_set(dup, base_dir, dry_run=args.dry_run)

        for key in total_stats:
            total_stats[key] += stats[key]

    # Step 3: Merge duplicate artwork files that now point to the same image
    print("\n" + "=" * 50)
    print("Merging duplicate artwork files...")
    artworks_dir = base_dir / "_artworks"
    artwork_stats = merge_duplicate_artworks(artworks_dir, dry_run=args.dry_run)

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Image files deleted: {total_stats['files_deleted']}")
    print(f"  Image files renamed: {total_stats['files_renamed']}")
    print(f"  References updated: {total_stats['refs_updated']}")
    print(f"  Artwork sets merged: {artwork_stats['artworks_merged']}")
    print(f"  Artwork files deleted: {artwork_stats['artworks_deleted']}")

    if args.dry_run:
        print("\nThis was a dry run. Use without --dry-run to apply changes.")

    return 0


if __name__ == "__main__":
    exit(main())
