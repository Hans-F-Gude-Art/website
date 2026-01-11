#!/usr/bin/env python3
"""
Safely rename artwork files to match their titles.

This script renames both the markdown file and the associated image file,
updates the image path in the markdown, and updates any references in
_data/galleries/*.yml files.

SAFETY FEATURES:
- Builds complete rename plan before any changes
- Detects collisions across the entire plan
- Skips artworks with duplicate titles
- Warns when image filename is more descriptive than title
- Dry-run by default (requires --execute to apply)

Usage:
    uv run python3 _scripts/rename_artworks.py            # Preview changes (dry-run)
    uv run python3 _scripts/rename_artworks.py --execute  # Apply changes
"""

import argparse
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
ARTWORKS_DIR = PROJECT_ROOT / "_artworks"
ASSETS_DIR = PROJECT_ROOT / "assets" / "images" / "galleries"
DATA_GALLERIES_DIR = PROJECT_ROOT / "_data" / "galleries"


@dataclass
class RenamePlan:
    """A planned rename operation."""
    md_file: Path
    new_md_name: str
    image_file: Path | None
    new_image_name: str | None
    title: str
    warnings: list[str]
    skip_reason: str | None = None


def slugify(title: str) -> str:
    """Convert a title to a URL-friendly slug."""
    # Normalize unicode characters
    slug = unicodedata.normalize("NFKD", title)
    slug = slug.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    slug = slug.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove anything that's not alphanumeric or hyphen
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    return slug


def is_filename_title(title: str) -> bool:
    """Check if a title looks like it's still an original filename."""
    # Ends with common image extensions
    if re.search(r"\.(jpg|jpeg|png|gif)$", title, re.IGNORECASE):
        return True

    # Looks like a date-based camera filename (e.g., 20140822_131431a)
    if re.match(r"^\d{8}[-_]\d+", title):
        return True

    # Looks like IMG_xxxx pattern
    if re.match(r"^img[-_]\d+", title, re.IGNORECASE):
        return True

    return False


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    frontmatter_str = content[4:end_match.start() + 3]
    body = content[end_match.end() + 3:]

    # Simple YAML parsing for our needs
    frontmatter = {}
    current_key = None
    current_list = None

    for line in frontmatter_str.split("\n"):
        if line.startswith("  - "):
            # List item
            if current_list is not None:
                current_list.append(line[4:].strip())
        elif ": " in line or line.endswith(":"):
            if current_list is not None:
                frontmatter[current_key] = current_list
                current_list = None

            if ": " in line:
                key, value = line.split(": ", 1)
                value = value.strip().strip('"').strip("'")
                frontmatter[key] = value
                current_key = key
            else:
                # Key with list value
                current_key = line[:-1]
                current_list = []

    if current_list is not None:
        frontmatter[current_key] = current_list

    return frontmatter, body


def image_name_seems_better(image_name: str, title_slug: str) -> bool:
    """Check if the image filename seems more descriptive than the title slug."""
    # Strip extension from image name
    image_slug = Path(image_name).stem

    # If image name has meaningful words and title doesn't, image is better
    image_words = set(image_slug.replace("-", " ").split())
    title_words = set(title_slug.replace("-", " ").split())

    # Remove common non-descriptive words
    generic_words = {"jpg", "jpeg", "png", "img", "image", "photo", "pic"}
    image_words -= generic_words
    title_words -= generic_words

    # If image has more unique descriptive words, it's probably better
    if len(image_words) > len(title_words) + 2:
        return True

    # Check for specific descriptive patterns in image but not title
    descriptive_patterns = ["hotel", "roofline", "village", "portrait", "study", "view"]
    for pattern in descriptive_patterns:
        if pattern in image_slug.lower() and pattern not in title_slug.lower():
            return True

    return False


def build_rename_plan(md_files: list[Path]) -> list[RenamePlan]:
    """Build a complete rename plan, checking for collisions."""
    plans: list[RenamePlan] = []

    # First pass: collect all titles and check for duplicates
    title_to_files: dict[str, list[Path]] = {}
    file_to_title: dict[Path, str] = {}
    file_to_image: dict[Path, str] = {}

    for md_file in md_files:
        content = md_file.read_text()
        frontmatter, _ = parse_frontmatter(content)

        title = frontmatter.get("title", "")
        image_path = frontmatter.get("image", "")

        if title:
            file_to_title[md_file] = title
            title_lower = title.lower()
            if title_lower not in title_to_files:
                title_to_files[title_lower] = []
            title_to_files[title_lower].append(md_file)

        if image_path:
            file_to_image[md_file] = image_path

    # Find duplicate titles
    duplicate_titles = {t for t, files in title_to_files.items() if len(files) > 1}

    # Track planned new names to detect plan-internal collisions
    planned_md_names: dict[str, Path] = {}  # new_name -> original file
    planned_image_names: dict[str, Path] = {}  # new_name -> original file

    # Second pass: build plans
    for md_file in md_files:
        title = file_to_title.get(md_file, "")
        image_path = file_to_image.get(md_file, "")

        if not title or not image_path:
            continue

        warnings: list[str] = []
        skip_reason: str | None = None

        # Check if title still looks like a filename
        if is_filename_title(title):
            skip_reason = "Title looks like a filename"
            plans.append(RenamePlan(
                md_file=md_file,
                new_md_name="",
                image_file=None,
                new_image_name=None,
                title=title,
                warnings=warnings,
                skip_reason=skip_reason,
            ))
            continue

        # Check for duplicate titles
        if title.lower() in duplicate_titles:
            skip_reason = f"Duplicate title (used by {len(title_to_files[title.lower()])} files)"
            plans.append(RenamePlan(
                md_file=md_file,
                new_md_name="",
                image_file=None,
                new_image_name=None,
                title=title,
                warnings=warnings,
                skip_reason=skip_reason,
            ))
            continue

        # Generate new slug
        new_slug = slugify(title)
        current_slug = md_file.stem

        # Skip if already correctly named
        if new_slug == current_slug:
            continue

        # Skip empty slugs
        if not new_slug:
            skip_reason = "Empty slug generated"
            plans.append(RenamePlan(
                md_file=md_file,
                new_md_name="",
                image_file=None,
                new_image_name=None,
                title=title,
                warnings=warnings,
                skip_reason=skip_reason,
            ))
            continue

        new_md_name = f"{new_slug}.md"

        # Check for collision with existing files
        new_md_path = md_file.parent / new_md_name
        if new_md_path.exists() and new_md_path != md_file:
            skip_reason = f"Target file already exists: {new_md_name}"
            plans.append(RenamePlan(
                md_file=md_file,
                new_md_name="",
                image_file=None,
                new_image_name=None,
                title=title,
                warnings=warnings,
                skip_reason=skip_reason,
            ))
            continue

        # Check for collision with other planned renames
        if new_md_name in planned_md_names:
            skip_reason = f"Collision with planned rename of {planned_md_names[new_md_name].name}"
            plans.append(RenamePlan(
                md_file=md_file,
                new_md_name="",
                image_file=None,
                new_image_name=None,
                title=title,
                warnings=warnings,
                skip_reason=skip_reason,
            ))
            continue

        planned_md_names[new_md_name] = md_file

        # Handle image file
        image_path_obj = Path(image_path)
        image_ext = image_path_obj.suffix
        gallery_id = image_path_obj.parent.name

        old_image_file = ASSETS_DIR / gallery_id / image_path_obj.name
        new_image_name = f"{new_slug}{image_ext}"
        new_image_file = ASSETS_DIR / gallery_id / new_image_name

        image_file: Path | None = None
        final_new_image_name: str | None = None

        if old_image_file.exists():
            # Check if image name seems more descriptive
            if image_name_seems_better(old_image_file.name, new_slug):
                warnings.append(f"Image name '{old_image_file.name}' may be more descriptive than '{new_image_name}'")

            if old_image_file == new_image_file:
                # Image already has correct name
                pass
            elif new_image_file.exists():
                warnings.append(f"Image target already exists: {new_image_name}")
            elif new_image_name in planned_image_names:
                warnings.append(f"Image collision with planned rename of {planned_image_names[new_image_name].name}")
            else:
                image_file = old_image_file
                final_new_image_name = new_image_name
                planned_image_names[new_image_name] = md_file
        else:
            warnings.append(f"Image file not found: {old_image_file.name}")

        plans.append(RenamePlan(
            md_file=md_file,
            new_md_name=new_md_name,
            image_file=image_file,
            new_image_name=final_new_image_name,
            title=title,
            warnings=warnings,
        ))

    return plans


def git_mv(src: Path, dst: Path) -> bool:
    """Move a file using git mv."""
    if not src.exists():
        return False

    result = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def update_image_path_in_file(filepath: Path, old_image: str, new_image: str) -> None:
    """Update the image path in a markdown file."""
    content = filepath.read_text()
    new_content = content.replace(old_image, new_image)
    filepath.write_text(new_content)


def update_gallery_data_files(old_slug: str, new_slug: str) -> list[str]:
    """Update references in _data/galleries/*.yml files."""
    changes = []

    for yml_file in DATA_GALLERIES_DIR.glob("*.yml"):
        content = yml_file.read_text()
        if old_slug in content:
            new_content = content.replace(f"- {old_slug}", f"- {new_slug}")
            if new_content != content:
                changes.append(str(yml_file.relative_to(PROJECT_ROOT)))
                yml_file.write_text(new_content)

    return changes


def execute_plan(plan: RenamePlan) -> list[str]:
    """Execute a single rename plan. Returns list of actions taken."""
    actions = []

    old_slug = plan.md_file.stem
    new_slug = Path(plan.new_md_name).stem

    # Rename markdown file
    new_md_path = plan.md_file.parent / plan.new_md_name
    if git_mv(plan.md_file, new_md_path):
        actions.append(f"git mv {plan.md_file.name} {plan.new_md_name}")
    else:
        actions.append(f"ERROR: Failed to move {plan.md_file.name}")
        return actions

    # Rename image file if needed
    if plan.image_file and plan.new_image_name:
        new_image_path = plan.image_file.parent / plan.new_image_name
        if git_mv(plan.image_file, new_image_path):
            actions.append(f"git mv {plan.image_file.name} {plan.new_image_name}")

            # Update image path in markdown
            old_image_path = f"/assets/images/galleries/{plan.image_file.parent.name}/{plan.image_file.name}"
            new_image_path_str = f"/assets/images/galleries/{plan.image_file.parent.name}/{plan.new_image_name}"
            update_image_path_in_file(new_md_path, old_image_path, new_image_path_str)
            actions.append(f"Updated image path in {plan.new_md_name}")
        else:
            actions.append(f"ERROR: Failed to move image {plan.image_file.name}")

    # Update gallery data files
    data_changes = update_gallery_data_files(old_slug, new_slug)
    for change in data_changes:
        actions.append(f"Updated {change}")

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Safely rename artwork files to match titles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Safety features:
  - Builds complete rename plan before any changes
  - Detects collisions across the entire plan
  - Skips artworks with duplicate titles
  - Warns when image filename seems more descriptive than title
  - Dry-run by default (preview mode)
        """,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually apply changes (default is dry-run preview)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    args = parser.parse_args()

    if not args.execute:
        print("=== DRY RUN - No changes will be made ===")
        print("    Use --execute to apply changes\n")

    md_files = sorted(ARTWORKS_DIR.glob("*.md"))

    if args.limit:
        md_files = md_files[:args.limit]

    print(f"Building rename plan for {len(md_files)} files...\n")

    plans = build_rename_plan(md_files)

    # Separate plans by type
    will_rename = [p for p in plans if p.new_md_name and not p.skip_reason]
    skipped = [p for p in plans if p.skip_reason]
    with_warnings = [p for p in will_rename if p.warnings]

    # Report skipped
    if skipped:
        print(f"=== SKIPPED ({len(skipped)} files) ===")
        for plan in skipped[:20]:
            print(f"  {plan.md_file.name}: {plan.skip_reason}")
        if len(skipped) > 20:
            print(f"  ... and {len(skipped) - 20} more")
        print()

    # Report warnings
    if with_warnings:
        print(f"=== WARNINGS ({len(with_warnings)} files) ===")
        for plan in with_warnings:
            print(f"  {plan.md_file.name} -> {plan.new_md_name}")
            for warning in plan.warnings:
                print(f"    WARNING: {warning}")
        print()

    # Report renames
    if will_rename:
        print(f"=== WILL RENAME ({len(will_rename)} files) ===")
        for plan in will_rename[:30]:
            print(f"\n{plan.md_file.name} -> {plan.new_md_name}")
            print(f"  Title: {plan.title}")
            if plan.image_file and plan.new_image_name:
                print(f"  Image: {plan.image_file.name} -> {plan.new_image_name}")

        if len(will_rename) > 30:
            print(f"\n  ... and {len(will_rename) - 30} more")

    # Execute if requested
    if args.execute and will_rename:
        print(f"\n=== EXECUTING {len(will_rename)} RENAMES ===")
        for plan in will_rename:
            print(f"\nRenaming {plan.md_file.name}...")
            actions = execute_plan(plan)
            for action in actions:
                print(f"  {action}")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"  Total files scanned: {len(md_files)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  With warnings: {len(with_warnings)}")
    print(f"  {'Renamed' if args.execute else 'Would rename'}: {len(will_rename)}")

    if not args.execute and will_rename:
        print(f"\nRun with --execute to apply these changes")


if __name__ == "__main__":
    main()
