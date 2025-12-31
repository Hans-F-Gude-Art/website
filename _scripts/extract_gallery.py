#!/usr/bin/env python3
"""
Extract gallery images and metadata from WIX HTML files.

Usage:
    python extract_gallery.py <html_file> <gallery_name> [--output-dir DIR] [--download]

Example:
    python extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-berkeley-campus.html campus-drawings --download
"""

import argparse
import os
import re
import sys
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple


class GalleryImage(NamedTuple):
    """Represents an image in the gallery."""
    title: str
    original_url: str
    filename: str


def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to a URL/filename-friendly slug."""
    # Lowercase
    slug = text.lower()
    # Replace special characters and spaces with hyphens
    slug = re.sub(r"['\",\(\)\[\]&]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate if too long
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def extract_original_url(wix_url: str) -> str | None:
    """
    Extract the original quality URL from a Wix CDN URL.

    Input:  static.wixstatic.com/media/f11310_abc.jpg/v1/fit/w_305,h_305/...
    Output: https://static.wixstatic.com/media/f11310_abc.jpg
    """
    # Handle URL-encoded tildes
    wix_url = urllib.parse.unquote(wix_url)

    # Match the pattern up to /v1/
    match = re.search(r"static\.wixstatic\.com/media/([^/]+\.(jpg|jpeg|png|gif|webp))", wix_url, re.IGNORECASE)
    if match:
        return f"https://static.wixstatic.com/media/{match.group(1)}"
    return None


class GalleryHTMLParser(HTMLParser):
    """Parse WIX HTML to extract gallery images."""

    def __init__(self):
        super().__init__()
        self.images: list[GalleryImage] = []
        self.seen_urls: set[str] = set()
        self.current_aria_label: str | None = None
        self._in_gallery_item = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = dict(attrs)

        # Look for gallery-item-container with aria-label
        if attrs_dict.get("class", "").find("gallery-item-container") >= 0:
            aria_label = attrs_dict.get("aria-label")
            if aria_label and aria_label not in ("top of page", "bottom of page", "Site"):
                self.current_aria_label = aria_label
                self._in_gallery_item = True

        # Look for images with wixstatic URLs
        if tag == "img" and self._in_gallery_item and self.current_aria_label:
            src = attrs_dict.get("src", "")
            if "static.wixstatic.com" in src:
                original_url = extract_original_url(src)
                if original_url and original_url not in self.seen_urls:
                    self.seen_urls.add(original_url)

                    # Determine file extension from URL
                    ext = Path(original_url).suffix or ".jpg"

                    # Create slug from aria-label
                    slug = slugify(self.current_aria_label)

                    # Handle duplicates
                    base_filename = f"{slug}{ext}"
                    filename = base_filename
                    counter = 1
                    existing_filenames = {img.filename for img in self.images}
                    while filename in existing_filenames:
                        counter += 1
                        filename = f"{slug}-{counter}{ext}"

                    self.images.append(GalleryImage(
                        title=self.current_aria_label,
                        original_url=original_url,
                        filename=filename,
                    ))

    def handle_endtag(self, tag: str):
        if tag == "div":
            # Reset when leaving a container (simplified)
            pass


def parse_html_file(filepath: Path) -> list[GalleryImage]:
    """Parse an HTML file and extract gallery images."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parser = GalleryHTMLParser()
    parser.feed(content)
    return parser.images


def download_image(url: str, output_path: Path) -> bool:
    """Download an image from URL to output path."""
    try:
        # Add headers to avoid 403
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; gallery-extractor/1.0)"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"  Error downloading {url}: {e}", file=sys.stderr)
        return False


def generate_yaml(images: list[GalleryImage], gallery_name: str) -> str:
    """Generate YAML content for the gallery."""
    lines = []
    for img in images:
        # Escape quotes in alt text
        alt_escaped = img.title.replace('"', '\\"')
        lines.append(f'- image: {gallery_name}/{img.filename}')
        lines.append(f'  alt: "{alt_escaped}"')
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extract gallery images from WIX HTML files"
    )
    parser.add_argument("html_file", type=Path, help="Path to the WIX HTML file")
    parser.add_argument("gallery_name", help="Name for the gallery (used in paths)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output directory for images and YAML"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download images (otherwise just generate YAML)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it"
    )

    args = parser.parse_args()

    if not args.html_file.exists():
        print(f"Error: File not found: {args.html_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {args.html_file}...")
    images = parse_html_file(args.html_file)
    print(f"Found {len(images)} images")

    if not images:
        print("No images found!")
        sys.exit(0)

    # Set up output paths
    images_dir = args.output_dir / "assets" / "images" / "galleries" / args.gallery_name
    data_dir = args.output_dir / "_data" / "galleries"
    yaml_path = data_dir / f"{args.gallery_name.replace('-', '_')}.yml"

    if args.dry_run:
        print(f"\nWould create directory: {images_dir}")
        print(f"Would create YAML file: {yaml_path}")
        print("\nImages to download:")
        for img in images:
            print(f"  {img.filename}: {img.title}")
            print(f"    URL: {img.original_url}")
        print("\nYAML content:")
        print(generate_yaml(images, args.gallery_name))
        return

    # Create directories
    images_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Download images if requested
    if args.download:
        print(f"\nDownloading images to {images_dir}...")
        for i, img in enumerate(images, 1):
            output_path = images_dir / img.filename
            if output_path.exists():
                print(f"  [{i}/{len(images)}] Skipping (exists): {img.filename}")
            else:
                print(f"  [{i}/{len(images)}] Downloading: {img.filename}")
                download_image(img.original_url, output_path)

    # Generate YAML
    yaml_content = generate_yaml(images, args.gallery_name)
    print(f"\nWriting YAML to {yaml_path}...")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    print("\nDone!")
    print(f"  Images: {images_dir}")
    print(f"  YAML:   {yaml_path}")


if __name__ == "__main__":
    main()
