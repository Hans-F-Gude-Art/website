#!/usr/bin/env python3
"""
Add suggested titles to artworks with duplicate/generic titles.

Usage:
    uv run python3 _scripts/add_title_suggestions.py
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ARTWORKS_DIR = PROJECT_ROOT / "_artworks"
STATUS_FILE = PROJECT_ROOT / "_scripts" / "title_review_status.json"

# Suggested titles for each artwork file
SUGGESTIONS = {
    # Female figure (14 files) - life drawings on various papers
    "female-figure.md": "Seated Nude with Hat in Profile",
    "female-figure-2.md": "Standing Figure, Three-Quarter View",
    "female-figure-4.md": "Reclining Nude with Long Hair and Jacket",
    "female-figure-5.md": "Crouching Figure from Behind",
    "female-figure-6.md": "Standing Nude with Short Hair",
    "female-figure-7.md": "Portrait Study in Profile with Natural Hair",
    "female-figure-8.md": "Torso Study with Arms Raised",
    "female-figure-9.md": "Standing Figure in Pencil",
    "female-figure-10.md": "Bust Study with Hair Up",
    "female-figure-11.md": "Reclining Figure with Long Straight Hair",
    "female-figure-12.md": "Figure Leaning on Pedestal",
    "female-figure-13.md": "Seated Figure in Wooden Rocking Chair",
    "female-figure-14.md": "Anatomical Studies of Legs and Torso",
    "female-figure-15.md": "Seated Figure with Legs Extended",

    # Rowing Study (11 files including case variants)
    "rowing-study.md": "Cal Rower Studies with Hand Detail",
    "rowing-study-2.md": "Rower from Behind in Pencil",
    "rowing-study-3.md": "Coach with Megaphone and Crew",
    "rowing-study-4.md": "Rower and Arm Study in Boathouse",
    "rowing-study-5.md": "Single Sculler with Cal Oar Blade",
    "rowing-study-6.md": "Crew Perspective Study with Grid",
    "rowing-study-7.md": "Eight-Man Shell from Above",
    "rowing-study-8.md": "Perspective Study with Color Grid",
    "rowing-study-9.md": "Rowers in Motion Study",
    "rowing-study-10.md": "Cal Crew Rowing Formation",
    "rowing-study-11.md": "Boathouse and Shell Study",

    # Charcoal with white highlights (4 files)
    "charcoal-with-white-highlights-on-toned-butcher-paper.md": "Figure Study on Ochre Paper",
    "charcoal-with-white-highlights-on-toned-butcher-paper-2.md": "Standing Figure on Toned Paper",
    "charcoal-with-white-highlights-on-toned-butcher-paper-3.md": "Seated Figure on Brown Paper",
    "charcoal-with-white-highlights-on-toned-butcher-paper-4.md": "Reclining Figure on Warm Paper",

    # Pencil on Paper (5 files including case variant)
    "pencil-on-paper.md": "Campus Scene in Pencil",
    "pencil-on-paper-3.md": "Figure Study in Graphite",
    "pencil-on-paper-5.md": "Architectural Sketch in Pencil",
    "pencil-on-paper-6.md": "Portrait Study in Graphite",
    "pencil-on-paper-7.md": "Landscape in Pencil",

    # Study of Mt. Diablo (4 files)
    "study-of-mt-diablo.md": "Mt. Diablo Morning Light Study",
    "study-of-mt-diablo-3.md": "Mt. Diablo from the East",
    "study-of-mt-diablo-4.md": "Mt. Diablo Sunset Colors",
    "study-of-mt-diablo-5.md": "Mt. Diablo with Cloud Shadows",

    # Sunrise Over Mt. Diablo (4 files)
    "sunrise-over-mt-diablo.md": "Sunrise Over Mt. Diablo with Orange Clouds",
    "sunrise-over-mt-diablo-2.md": "Sunrise Over Mt. Diablo, Misty Morning",
    "sunrise-over-mt-diablo-3.md": "Sunrise Over Mt. Diablo, Clear Sky",
    "sunrise-over-mt-diablo-4.md": "Sunrise Over Mt. Diablo, Purple Haze",

    # Hotel Side Door (3 files)
    "hotel-side-door.md": "Viking Village Hotel Side Entrance",
    "hotel-side-door-2.md": "Hotel Side Door with Shadows",
    "hotel-side-door-3.md": "Hotel Side Door in Afternoon Light",

    # Blue Boat (2 files)
    "blue-boat.md": "Blue Boat at Anchor",
    "blue-boat-2.md": "Blue Boat in Harbor",

    # Boats (2 files)
    "boats.md": "Boats at the Dock",
    "boats-2.md": "Boats in Morning Mist",

    # Bridge Over Strawberry Creek (2 files)
    "bridge-over-strawberry-creek.md": "Stone Bridge Over Strawberry Creek",
    "bridge-over-strawberry-creek-2.md": "Wooden Bridge Over Strawberry Creek",

    # Emily at 21 (2 files)
    "emily-at-21.md": "Emily at 21, Portrait",
    "emily-at-21-2.md": "Emily at 21, Three-Quarter View",

    # Flowers (2 files)
    "flowers.md": "Flowers in Glass Vase",
    "flowers-2.md": "Wildflowers in Ceramic Pot",

    # Imperial Palace (2 files)
    "imperial-palace.md": "Imperial Palace, Front View",
    "imperial-palace-2.md": "Imperial Palace Gardens",

    # Mt. Diablo at Sunset detail (2 files)
    "mt-diablo-at-sunset-detail.md": "Mt. Diablo at Sunset, Sky Detail",
    "mt-diablo-at-sunset-detail-2.md": "Mt. Diablo at Sunset, Mountain Detail",

    # Office and Hotel (2 files)
    "office-and-hotel.md": "Viking Village Office and Hotel",
    "office-and-hotel-2.md": "Office and Hotel at Dusk",

    # Oil on Canvas (2 files)
    "oil-on-canvas.md": "Landscape Oil Study",
    "oil-on-canvas-3.md": "Figure Oil Study",

    # Plant (2 files)
    "plant.md": "Potted Plant by Window",
    "plant-2.md": "Snake Plant in Corner",

    # Sather Tower (2 files)
    "sather-tower-campanile-university-of-california-berkeley.md": "Sather Tower from South Hall",
    "sather-tower-campanile-university-of-california-berkeley-2.md": "Sather Tower Through the Trees",

    # Self-Portrait as Maldoror (2 files)
    "self-portrait-as-maldoror-or-self-portrait-in-broken-glass.md": "Self-Portrait as Maldoror, Full View",
    "self-portrait-as-maldoror-or-self-portrait-in-broken-glass-3.md": "Self-Portrait in Broken Glass, Detail",

    # Snack Shack (2 files)
    "snack-shack.md": "Viking Village Snack Shack",
    "snack-shack-2.md": "Snack Shack with Customers",

    # Statue on facade of Hearst (2 files)
    "statue-on-facade-of-hearst-memorial-mining-building.md": "Hearst Mining Building Statue, Left",
    "statue-on-facade-of-hearst-memorial-mining-building-2.md": "Hearst Mining Building Statue, Right",

    # Still Life with Silver Tea Pot (2 files)
    "still-life-with-silver-tea-pot-baseball-and-diplodocus.md": "Still Life with Silver Tea Pot, Oil",
    "still-life-with-silver-tea-pot-baseball-and-diplodocus-2.md": "Still Life with Silver Tea Pot, Drawing",

    # Study of Boat in Belize Harbor (2 files)
    "study-of-boat-in-belize-harbor.md": "Boat in Belize Harbor, Morning",
    "study-of-boat-in-belize-harbor-2.md": "Boat in Belize Harbor, Afternoon",

    # Watercolor (2 files)
    "watercolor.md": "Watercolor Landscape Study",
    "watercolor-3.md": "Viking Village Hotel Roofline",

    # Yosemite Valley (2 files)
    "yosemite-valley.md": "Yosemite Valley, After Bierstadt",
    "yosemite-valley-2.md": "Yosemite Valley, Watercolor Study",

    # University House (1 file - generic title)
    "university-house-uc-berkeley.md": "University House, UC Berkeley, Pencil Study",
}


def add_suggestion_to_artwork(filepath: Path, suggested_title: str) -> bool:
    """Add suggested_title to artwork frontmatter."""
    content = filepath.read_text()

    # Check if already has suggested_title
    if "suggested_title:" in content:
        return False

    # Insert suggested_title after title line
    new_content = re.sub(
        r'^(title: "[^"]*")\n',
        f'\\1\nsuggested_title: "{suggested_title}"\n',
        content,
        count=1,
        flags=re.MULTILINE
    )

    if new_content == content:
        # Try without quotes
        new_content = re.sub(
            r"^(title: '[^']*')\n",
            f'\\1\nsuggested_title: "{suggested_title}"\n',
            content,
            count=1,
            flags=re.MULTILINE
        )

    if new_content != content:
        filepath.write_text(new_content)
        return True
    return False


def update_status_file(suggestions: dict[str, str]) -> None:
    """Update the status file to mark artworks as has_suggestion."""
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        status = json.load(f)

    updated_count = 0
    for filename, suggested_title in suggestions.items():
        if filename in status["artworks"]:
            artwork = status["artworks"][filename]
            if artwork.get("status") == "needs_review":
                artwork["status"] = "has_suggestion"
                artwork["suggested_title"] = suggested_title
                status["statistics"]["needs_review"] -= 1
                status["statistics"]["has_suggestion"] += 1
                updated_count += 1

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    print(f"Updated {updated_count} artworks in status file")


def main():
    print(f"Adding suggestions to {len(SUGGESTIONS)} artworks...\n")

    success = 0
    skipped = 0
    missing = 0

    for filename, suggested_title in SUGGESTIONS.items():
        filepath = ARTWORKS_DIR / filename
        if not filepath.exists():
            print(f"  MISSING: {filename}")
            missing += 1
            continue

        if add_suggestion_to_artwork(filepath, suggested_title):
            print(f"  Added: {filename} -> {suggested_title}")
            success += 1
        else:
            print(f"  Skipped: {filename} (already has suggestion)")
            skipped += 1

    print(f"\nAdded suggestions to {success} artworks")
    print(f"Skipped {skipped} (already had suggestions)")
    print(f"Missing {missing} files")

    # Update status file
    update_status_file(SUGGESTIONS)


if __name__ == "__main__":
    main()
