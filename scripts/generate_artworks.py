#!/usr/bin/env python3
"""
Convert YAML gallery data files to Jekyll _artworks collection.

Reads _data/galleries/*.yml and generates _artworks/*.md files.

Usage:
    python scripts/generate_artworks.py
"""

import os
import re
from pathlib import Path
import yaml


def slugify(text: str) -> str:
    """Convert text to a filename-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"['\",\(\)\[\]&]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    # Truncate if too long
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0]
    return slug


def yaml_filename_to_gallery_id(filename: str) -> str:
    """Convert YAML filename to gallery ID.

    Example: campus_drawings.yml -> campus-drawings
    """
    name = Path(filename).stem  # Remove .yml
    return name.replace("_", "-")


def generate_artwork_md(title: str, image: str, galleries: list[str]) -> str:
    """Generate markdown content for an artwork."""
    # Escape quotes in title for YAML
    title_escaped = title.replace('"', '\\"')

    galleries_yaml = "\n".join(f"  - {g}" for g in galleries)

    return f"""---
layout: artwork
title: "{title_escaped}"
image: {image}
galleries:
{galleries_yaml}
---
"""


def main():
    # Paths
    data_dir = Path("_data/galleries")
    artworks_dir = Path("_artworks")

    # Create artworks directory
    artworks_dir.mkdir(exist_ok=True)

    # Track all artworks by image path to handle duplicates across galleries
    # Key: image path, Value: {title, galleries set}
    artworks: dict[str, dict] = {}

    # Read all YAML files
    yaml_files = sorted(data_dir.glob("*.yml"))
    print(f"Found {len(yaml_files)} gallery YAML files")

    for yaml_file in yaml_files:
        gallery_id = yaml_filename_to_gallery_id(yaml_file.name)

        with open(yaml_file, "r", encoding="utf-8") as f:
            items = yaml.safe_load(f)

        if not items:
            print(f"  Skipping empty file: {yaml_file.name}")
            continue

        print(f"  {yaml_file.name}: {len(items)} artworks -> gallery '{gallery_id}'")

        for item in items:
            image = item.get("image", "")
            title = item.get("alt", "Untitled")

            if not image:
                continue

            if image in artworks:
                # Artwork already exists, add this gallery
                artworks[image]["galleries"].add(gallery_id)
            else:
                # New artwork
                artworks[image] = {
                    "title": title,
                    "galleries": {gallery_id}
                }

    print(f"\nTotal unique artworks: {len(artworks)}")

    # Count multi-gallery artworks
    multi_gallery = sum(1 for a in artworks.values() if len(a["galleries"]) > 1)
    if multi_gallery:
        print(f"Artworks in multiple galleries: {multi_gallery}")

    # Generate markdown files
    print(f"\nGenerating markdown files in {artworks_dir}/...")

    # Track filenames to handle duplicates
    used_filenames: set[str] = set()

    for image, data in artworks.items():
        # Create slug from title
        base_slug = slugify(data["title"])
        if not base_slug:
            # Fallback to image filename
            base_slug = slugify(Path(image).stem)

        # Ensure unique filename
        slug = base_slug
        counter = 1
        while slug in used_filenames:
            counter += 1
            slug = f"{base_slug}-{counter}"
        used_filenames.add(slug)

        # Sort galleries for consistent output
        galleries = sorted(data["galleries"])

        # Generate content
        content = generate_artwork_md(data["title"], image, galleries)

        # Write file
        output_path = artworks_dir / f"{slug}.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"Generated {len(artworks)} artwork files")
    print("\nDone!")


if __name__ == "__main__":
    main()
