#!/usr/bin/env python3
"""
Triage artwork titles to identify files needing review.

Scans _artworks/*.md and identifies titles that appear to be filenames,
timestamps, nonsense strings, duplicate titles, or other non-descriptive patterns.

Usage:
    uv run python3 _scripts/triage_titles.py
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# Generic titles that are too vague to be useful as unique identifiers
GENERIC_TITLES = {
    "watercolor",
    "oil on canvas",
    "pencil on paper",
    "charcoal on paper",
    "ink on paper",
    "pastel",
    "gouache",
    "acrylic",
    "mixed media",
    "untitled",
    "study",
    "sketch",
    "drawing",
    "painting",
    "portrait",
    "landscape",
    "still life",
    "figure",
    "nude",
    "abstract",
}


# Bad title patterns with classification reasons
PATTERNS = {
    # File extensions at end of title
    "file_extension": re.compile(r"\.(jpg|jpeg|png|gif|bmp|tiff?)$", re.IGNORECASE),

    # Camera prefixes (IMG_, CIMG, PXL_, DSC, etc.)
    "camera_prefix": re.compile(r"^(IMG_|CIMG|PXL_|DSC|DSCN|DSCF|P\d{6,})", re.IGNORECASE),

    # Timestamp patterns (YYYYMMDD, YYYYMMDD_HHMMSS, etc.)
    "timestamp": re.compile(r"^20\d{6}[_-]?\d*"),

    # URL encoding (%20, %3B, etc.)
    "url_encoded": re.compile(r"%[0-9A-Fa-f]{2}"),

    # Wix artifacts
    "wix_artifact": re.compile(r"(for wix|_edited|med res|to web)", re.IGNORECASE),

    # Flickr IDs (long numeric with underscores like 2772605131_800182b279_o)
    "flickr_id": re.compile(r"^\d{8,}_[a-f0-9]{8,}_[a-z]$", re.IGNORECASE),

    # Hash/UUID-like strings (long hex sequences)
    "hash_string": re.compile(r"[a-f0-9]{24,}", re.IGNORECASE),

    # Screenshot patterns
    "screenshot": re.compile(r"^screenshot", re.IGNORECASE),

    # Nonsense/keyboard mashing (short strings with no vowels or repeated patterns)
    "nonsense": re.compile(r"^[bcdfghjklmnpqrstvwxz]{4,}$", re.IGNORECASE),

    # Very short titles (likely abbreviated or incomplete)
    "too_short": re.compile(r"^.{1,3}$"),

    # Titles starting with underscore (likely filename artifacts)
    "underscore_prefix": re.compile(r"^_"),

    # Biography misspelling pattern from the data
    "biography_number": re.compile(r"bior?graphy\d+", re.IGNORECASE),
}


def classify_title(title: str, title_counts: Counter | None = None) -> tuple[bool, list[str]]:
    """
    Check if a title is a bad (non-descriptive) title.

    Args:
        title: The title to check
        title_counts: Counter of all titles (for duplicate detection)

    Returns:
        Tuple of (is_bad, list of reasons)
    """
    reasons = []

    # Strip whitespace for analysis
    title_stripped = title.strip()
    title_lower = title_stripped.lower()

    for pattern_name, pattern in PATTERNS.items():
        if pattern.search(title_stripped):
            reasons.append(pattern_name)

    # Additional heuristics

    # Check for titles that are mostly digits
    digit_ratio = sum(c.isdigit() for c in title_stripped) / max(len(title_stripped), 1)
    if digit_ratio > 0.5 and len(title_stripped) > 5:
        if "mostly_digits" not in reasons:
            reasons.append("mostly_digits")

    # Check for titles with suspicious character patterns (random keyboard mashing)
    # Look for lack of spaces in long titles that have file extension
    if len(title_stripped) > 10 and " " not in title_stripped:
        if any(r in reasons for r in ["file_extension", "camera_prefix"]):
            pass  # Already caught
        elif re.match(r"^[a-z0-9_-]+$", title_stripped, re.IGNORECASE):
            # Looks like a filename slug
            if "filename_pattern" not in reasons:
                reasons.append("filename_pattern")

    # Check for duplicate titles (same title used by multiple artworks)
    if title_counts and title_counts.get(title_lower, 0) > 1:
        reasons.append("duplicate_title")

    # Check for generic/vague titles
    if title_lower in GENERIC_TITLES:
        reasons.append("generic_title")

    return len(reasons) > 0, reasons


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}

    try:
        end = content.index("---", 3)
        yaml_content = content[3:end].strip()

        # Simple YAML parsing for title field
        result = {}
        for line in yaml_content.split("\n"):
            if line.startswith("title:"):
                # Extract title, handling quotes
                title = line[6:].strip()
                if title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                elif title.startswith("'") and title.endswith("'"):
                    title = title[1:-1]
                result["title"] = title
                break

        return result
    except ValueError:
        return {}


def load_existing_status(status_file: Path) -> dict:
    """Load existing status file if it exists."""
    if status_file.exists():
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    artworks_dir = Path("_artworks")
    status_file = Path("_scripts/title_review_status.json")

    if not artworks_dir.exists():
        print(f"Error: {artworks_dir} not found")
        return 1

    # Load existing status to preserve completed items
    existing_status = load_existing_status(status_file)
    existing_artworks = existing_status.get("artworks", {})

    # Scan all artwork files
    artwork_files = sorted(artworks_dir.glob("*.md"))
    print(f"Scanning {len(artwork_files)} artwork files...")

    # FIRST PASS: Collect all titles to detect duplicates
    print("Pass 1: Collecting titles for duplicate detection...")
    all_titles: dict[str, str] = {}  # filename -> title
    for artwork_file in artwork_files:
        with open(artwork_file, "r", encoding="utf-8") as f:
            content = f.read()
        frontmatter = parse_frontmatter(content)
        title = frontmatter.get("title", "")
        if title:
            all_titles[artwork_file.name] = title

    # Count title occurrences (case-insensitive)
    title_counts = Counter(t.lower() for t in all_titles.values())

    # Find duplicates for reporting
    duplicates = {title: count for title, count in title_counts.items() if count > 1}
    if duplicates:
        print(f"  Found {len(duplicates)} duplicate titles:")
        for title, count in sorted(duplicates.items(), key=lambda x: -x[1])[:10]:
            print(f"    '{title}' appears {count} times")
        if len(duplicates) > 10:
            print(f"    ... and {len(duplicates) - 10} more")

    # Results
    results = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "statistics": {
            "total": 0,
            "needs_review": 0,
            "has_suggestion": 0,
            "completed": 0,
            "good": 0,
        },
        "by_classification": {},
        "artworks": {},
    }

    # SECOND PASS: Classify each title
    print("Pass 2: Classifying titles...")
    for artwork_file in artwork_files:
        filename = artwork_file.name
        title = all_titles.get(filename, "")

        if not title:
            print(f"  Warning: No title found in {filename}")
            continue

        results["statistics"]["total"] += 1

        # Check if this artwork was already completed
        existing = existing_artworks.get(filename, {})
        if existing.get("status") == "completed":
            # Preserve completed status
            results["artworks"][filename] = existing
            results["statistics"]["completed"] += 1
            continue

        # Check if has suggestion already
        if existing.get("status") == "has_suggestion":
            results["artworks"][filename] = existing
            results["statistics"]["has_suggestion"] += 1
            continue

        # Classify the title (now with duplicate detection)
        is_bad, reasons = classify_title(title, title_counts)

        if is_bad:
            results["artworks"][filename] = {
                "status": "needs_review",
                "title": title,
                "reasons": reasons,
            }
            results["statistics"]["needs_review"] += 1

            # Track by classification
            for reason in reasons:
                if reason not in results["by_classification"]:
                    results["by_classification"][reason] = 0
                results["by_classification"][reason] += 1
        else:
            results["artworks"][filename] = {
                "status": "good",
                "title": title,
            }
            results["statistics"]["good"] += 1

    # Write results
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\nResults written to {status_file}")
    print(f"\nStatistics:")
    print(f"  Total artworks: {results['statistics']['total']}")
    print(f"  Good titles: {results['statistics']['good']}")
    print(f"  Needs review: {results['statistics']['needs_review']}")
    print(f"  Has suggestion: {results['statistics']['has_suggestion']}")
    print(f"  Completed: {results['statistics']['completed']}")

    if results["by_classification"]:
        print(f"\nBad titles by classification:")
        for reason, count in sorted(results["by_classification"].items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    return 0


if __name__ == "__main__":
    exit(main())
