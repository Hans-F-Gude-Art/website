#!/usr/bin/env python3
"""Fix mismatched slugs in gallery data files."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ARTWORKS_DIR = PROJECT_ROOT / "_artworks"
DATA_DIR = PROJECT_ROOT / "_data" / "galleries"

# Known fixes (bad slug -> correct slug)
FIXES = {
    "emily-at-21-portrait-three-quarter-view": "emily-at-21-three-quarter-view",
    "still-life-with-silver-tea-pot-baseball-and-diplodocus-detail-drawing": "still-life-with-silver-tea-pot-baseball-and-diplodocus-drawing",
    "sunrise-over-mt-diablo-with-orange-clouds-misty-morning": "sunrise-over-mt-diablo-misty-morning",
    "sunrise-over-mt-diablo-with-orange-clouds-clear-sky": "sunrise-over-mt-diablo-clear-sky",
    "sunrise-over-mt-diablo-with-orange-clouds-purple-haze": "sunrise-over-mt-diablo-purple-haze",
    "mt-diablo-morning-light-study-before-sunrise": "study-of-mt-diablo-before-sunrise",
    "imperial-palace-drawing-gardens": "imperial-palace-gardens",
    "yosemite-valley-in-oil-after-bierstadt-watercolor-study": "yosemite-valley-watercolor-study",
    "yosemite-valley-in-oil-after-bierstadt-after-bierstadt": "yosemite-valley-after-bierstadt",
    "imperial-palace-drawing-tokyo": "imperial-palace-tokyo",
    "blue-boat-on-the-dock-at-the-woodss-outside-the-snack-shack": "blue-boats-outside-the-snack-shack",
    "blue-boat-on-the-dock-at-the-woods-at-the-woods": "blue-boat-at-the-woods",
    "viking-village-hotel-side-entrance-with-shadows": "hotel-side-door-with-shadows",
    "university-house-uc-berkeley-pencil-study-drawing": "university-house-uc-berkeley-drawing",
    "viking-village-snack-shack-from-the-water": "snack-shack-from-the-water",
    "boat-mored-in-belize-harbor-afternoon": "study-of-boat-in-belize-harbor-afternoon",
    "viking-village-hotel-side-entrance-sketch": "hotel-side-door-sketch",
    "viking-village-office-and-hotel-linework": "office-and-hotel-linework",
    "over-the-backyard-fence-board-11-x-14-inches-28-x-36-cm": "over-the-backyard-fence",
    "flowers-in-glass-vase-in-ceramic-pot": "flowers-in-ceramic-pot",
    "portrait-of-a-girl-after-wm-chase-with-white-gouache-highlights-8-x-10": "portrait-of-a-girl-after-wm-chase",
    "view-towards-old-forge-from-the-docks-x-4-feet-10-x-13-m": "view-towards-old-forge-from-the-docks",
}

def fix_file(filepath):
    content = filepath.read_text()
    fixes = 0
    for bad, good in FIXES.items():
        if bad in content:
            content = content.replace(f"- {bad}", f"- {good}")
            print(f"  {filepath.name}: {bad} -> {good}")
            fixes += 1
    if fixes > 0:
        filepath.write_text(content)
    return fixes

def main():
    total = 0
    for yml_file in sorted(DATA_DIR.glob("*.yml")):
        fixes = fix_file(yml_file)
        total += fixes
    print(f"\nFixed {total} references")

if __name__ == "__main__":
    main()
