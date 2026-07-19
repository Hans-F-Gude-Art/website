#!/usr/bin/env python3
"""Tag artworks with a `mediums:` frontmatter list.

Derives mediums from two signals:
1. The artwork's `description` field (e.g. "Oil on Canvas, 16 x 16 inches")
2. Membership in medium-specific galleries (select-oils, pencil-drawings, ...)

The two signals are unioned. Highlight phrases ("with white gouache
highlights") are stripped before matching so accent media don't tag the work.
Digital works (Procreate) are tagged only `digital`, even when the
description names the simulated medium.

Usage:
    python3 _scripts/tag_mediums.py            # dry-run report
    python3 _scripts/tag_mediums.py --apply    # write mediums: to frontmatter
    python3 _scripts/tag_mediums.py --strip-retired  # also remove retired
                                               # gallery ids from galleries:
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ARTWORKS_DIR = Path(__file__).parent.parent / "_artworks"

# Gallery id -> medium implied by membership.
GALLERY_MEDIUMS = {
    "select-oils": "oil",
    "select-watercolors": "watercolor",
    "select-gouache": "gouache",
    "select-charcoal": "charcoal",
    "charcoal-drawings": "charcoal",
    "pencil-drawings": "pencil",
    "pen-ink-drawings": "pen-ink",
    "photographs": "photograph",
}

# Gallery ids retired by the by-medium refactor (curated lists replaced by
# derived pages). Removed from artwork `galleries:` with --strip-retired.
RETIRED_GALLERIES = {
    "select-oils",
    "select-watercolors",
    "select-gouache",
    "select-charcoal",
    "charcoal-drawings",
    "pencil-drawings",
    "pen-ink-drawings",
    "watercolor-gouache",
}

# Phrases describing accents/highlights, not the work's medium.
HIGHLIGHT_PHRASES = [
    r"with (white|blue) gouache( highlights)?",
    r"gouache highlights",
    r"white gouache",
    r"white charcoal",
    r"white acrylic highlights",
    r"ballpoint pen",
]

DESCRIPTION_MEDIUMS = [
    (r"\boils?\b", "oil"),
    (r"\bwatercolors?\b", "watercolor"),
    (r"\bgouache\b", "gouache"),
    (r"\bcharcoal\b", "charcoal"),
    (r"\bpencil\b|\bgraphite\b", "pencil"),
    (r"pen\s*(&|&amp;|and)\s*ink", "pen-ink"),
    (r"\bphotographs?\b", "photograph"),
]

MEDIUM_ORDER = [
    "oil", "watercolor", "gouache", "pen-ink",
    "charcoal", "pencil", "digital", "photograph",
]


def parse_frontmatter(text: str) -> tuple[dict, int, int]:
    """Return ({field: raw_value}, fm_start_line, fm_end_line) from raw text."""
    lines = text.split("\n")
    if lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fields = {}
    current = None
    for line in lines[1:end]:
        if re.match(r"^[A-Za-z_]+:", line):
            current = line.split(":", 1)[0]
            fields[current] = line.split(":", 1)[1].strip()
        elif current and line.startswith("  - "):
            fields.setdefault(current + "__list", []).append(line[4:].strip())
    return fields, 1, end


def mediums_from_description(description: str) -> set[str]:
    text = description.lower().strip().strip('"')
    for phrase in HIGHLIGHT_PHRASES:
        text = re.sub(phrase, "", text)
    if re.search(r"\bprocreate\b|\bdigital\b", text):
        return {"digital"}
    found = set()
    for pattern, medium in DESCRIPTION_MEDIUMS:
        if re.search(pattern, text):
            found.add(medium)
    return found


def process(apply: bool, strip_retired: bool) -> int:
    counts = Counter()
    untagged = []
    disagreements = []
    tagged_total = 0

    for path in sorted(ARTWORKS_DIR.glob("*.md")):
        text = path.read_text()
        fields, _, end = parse_frontmatter(text)
        description = fields.get("description", "")
        galleries = fields.get("galleries__list", [])

        from_desc = mediums_from_description(description) if description else set()
        from_gal = {GALLERY_MEDIUMS[g] for g in galleries if g in GALLERY_MEDIUMS}

        # Description is authoritative; gallery curation has known misfiles
        # (pencil studies filed under Select Oils).
        mediums = sorted(from_desc or from_gal, key=MEDIUM_ORDER.index)

        if from_desc and from_gal and not (from_desc & from_gal):
            disagreements.append((path.name, sorted(from_desc), sorted(from_gal)))

        if not mediums:
            untagged.append(path.name)
        else:
            tagged_total += 1
            for m in mediums:
                counts[m] += 1

        if apply:
            lines = text.split("\n")
            # Drop any existing mediums block.
            new_lines, in_mediums = [], False
            for i, line in enumerate(lines):
                if i <= end and line.startswith("mediums:"):
                    in_mediums = True
                    continue
                if in_mediums and line.startswith("  - "):
                    continue
                in_mediums = False
                new_lines.append(line)
            lines = new_lines
            end_idx = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")

            if strip_retired:
                kept, in_gal, gal_start = [], False, None
                for i, line in enumerate(lines):
                    if i < end_idx and line.startswith("galleries:"):
                        in_gal = True
                        gal_start = len(kept)
                        kept.append(line)
                        continue
                    if in_gal and line.startswith("  - "):
                        if line[4:].strip() not in RETIRED_GALLERIES:
                            kept.append(line)
                        continue
                    in_gal = False
                    kept.append(line)
                if gal_start is not None and (
                    gal_start + 1 >= len(kept) or not kept[gal_start + 1].startswith("  - ")
                ):
                    kept[gal_start] = "galleries: []"
                lines = kept
                end_idx = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")

            if mediums:
                block = ["mediums:"] + [f"  - {m}" for m in mediums]
                lines[end_idx:end_idx] = block
            path.write_text("\n".join(lines))

    print(f"tagged: {tagged_total}, untagged: {len(untagged)}")
    for medium in MEDIUM_ORDER:
        if counts[medium]:
            print(f"  {medium}: {counts[medium]}")
    if disagreements:
        print("\ndescription/gallery disagreements (description wins):")
        for name, d, g in disagreements:
            print(f"  {name}: description={d} galleries={g}")
    if untagged:
        print("\nuntagged:")
        for name in untagged:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--strip-retired", action="store_true")
    args = parser.parse_args()
    sys.exit(process(apply=args.apply, strip_retired=args.strip_retired))
