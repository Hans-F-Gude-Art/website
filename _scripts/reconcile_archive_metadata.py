#!/usr/bin/env python3
"""Match archive inventory items to repo artworks; emit reconciliation report.

Reads:
    _reports/archive_inventory.yml
    _artworks/*.md
    _data/galleries/*.yml

Writes:
    _reports/archive_reconciliation.yml

Usage:
    uv run --with pyyaml python3 _scripts/reconcile_archive_metadata.py [--fix-order]
"""

import argparse
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Run with: uv run --with pyyaml python3 ...")
    sys.exit(1)

ARTWORKS_DIR = Path("_artworks")
GALLERIES_DIR = Path("_data/galleries")
INVENTORY_FILE = Path("_reports/archive_inventory.yml")
RECONCILIATION_FILE = Path("_reports/archive_reconciliation.yml")

# ---------------------------------------------------------------------------
# Archive slug → repo gallery ID mapping
# Only includes pages that are 1:1 gallery mappings (confirmed by title spot-check
# and item count alignment). Hub pages (figures, drawings, landscapes) are omitted.
# ---------------------------------------------------------------------------

GALLERY_MAP: dict[str, str | None] = {
    # Direct matches (slug matches gallery id closely)
    "still-lifes": "still_lifes",
    "emily": "emily",
    "landscapes-mt-diablo": "landscapes_mt_diablo",
    "landscapes-other": "landscapes_other",
    "landscapes-outdoors": "landscapes_outdoors",
    "landscapes-watercolor-g": "landscapes_watercolor",
    "figures-paintings": "figure_paintings",
    "figures-figure-studies": "figure_studies",
    "figures-life-drawing-class": "life_drawing",
    "drawings-finished-drawings": "finished_drawings",
    "drawings-sketches-studies": "sketches_studies",
    "images-of-cal-sports": "cal_athletics",
    # copy-of-* pages (confirmed by title spot-check)
    "copy-of-the-play-drawings": "the_play_illustrations",
    "copy-of-campus-paintings": "oski_caricatures",
    "copy-of-campus-drawings": "illustrations",
    "copy-of-new-page": "viking_village",
    "copy-of-watercolor-gouache": "watercolor_gouache",
    "copy-of-rowing-drawings": "rowing_boathouse",
    "copy-of-rowing-drawings-1": "cal_rowing",
    "copy-of-rowing-drawings-2": "the_play",
    "copy-of-cal-marching-band": "cal_band_drawings",
    "copy-of-select-charcoal-drawings": "select_charcoal",
    "copy-of-finished-drawings": "select_charcoal",   # overlapping source
    "copy-of-sketches-studies": "perspective_studies",
    # v2: newly harvested pages (SSR + CDX fallback)
    "copy-of-berkeley-campus": "campus_drawings",
    "images-of-the-berkeley-campus": "uc_berkeley_campus",
    "photographs": "photographs",
    "copy-of-figure-drawings": "figure_drawings",
    "copy-of-figure-drawings-complete-fi": "figure_complete",
    "copy-of-finished-drawings-1": "finished_drawings",
    "copy-of-cal-marching-band-1": "cal_marching_band",
    "copy-of-select-watercolors-gouache": "select_watercolors",
    # Not mapped (hub pages, super-galleries with duplicated items, or genuinely empty):
    # landscapes, figures, drawings — super-galleries
    # copy-of-other-landscapes — mixed content
    # in-progress — 3 items already in other galleries
    # cal-campus, cal-men-s-rowing, copy-of-cal-men-s-rowing — no captures found
    # images-of-cal-marching-band — no captures found
    # uc-berkeley-artworks — no captures found
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a slug, matching the repo's extract_gallery.py convention.

    Removes apostrophes/quotes before hyphenating, so "Brynilsen's" -> "brynilsens".
    URL-decodes before processing.

    IMG_0032a.jpg -> img-0032a-jpg
    Oski Gothic.jpg -> oski-gothic-jpg
    Brynilsen's Viking Village -> brynilsens-viking-village
    """
    s = urllib.parse.unquote(text)
    s = s.lower()
    # Remove characters the repo strips (apostrophes, quotes, parens, brackets, &)
    s = re.sub(r"['\"‘’“”()\[\]&]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalize_title(title: str) -> str:
    """Normalize whitespace and common quote/dash variants for comparison."""
    title = title.strip()
    title = re.sub(r"\s+", " ", title)
    # Straight quotes only
    title = title.replace("‘", "'").replace("’", "'")
    title = title.replace("“", '"').replace("”", '"')
    # Em dash / en dash → regular hyphen for comparison
    title = title.replace("—", "--").replace("–", "-")
    return title


def _normalize_hash(h: str) -> str:
    """Return lowercase f11310_<hex> without ~mv2 for deduplication."""
    m = re.match(r"f11310_([0-9a-f]+)", h, re.IGNORECASE)
    return f"f11310_{m.group(1).lower()}" if m else h.lower()


def _normalize_for_match(title: str) -> str:
    """Aggressive normalization for fuzzy title matching.

    Lowercases; strips HTML entities, punctuation (except alphanumeric and
    spaces); strips leading 'the '; collapses whitespace.
    """
    t = title.strip()
    # Decode basic HTML entities
    t = t.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
    t = t.replace("&lt;", "<").replace("&gt;", ">")
    t = re.sub(r"&#\d+;", "", t)
    t = t.lower()
    # Normalize curly quotes and dashes
    t = t.replace("'", "'").replace("'", "'")
    t = t.replace(""", '"').replace(""", '"')
    t = t.replace("—", "-").replace("–", "-")
    # Strip punctuation (keep alphanumeric and spaces)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    # Strip leading 'the '
    t = re.sub(r"^the\s+", "", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_hash_index(inventory: dict[str, dict]) -> dict[str, dict]:
    """Collapse all inventory items to one record per normalized media hash.

    Title from warmup (has_description) preferred over SSR (title only).
    Description from warmup sources. original_filename from warmup.
    """
    records: dict[str, dict] = {}
    # Two passes: warmup items first so they win on conflict
    for pass_warmup in (True, False):
        for page_data in inventory.values():
            for item in page_data.get("items", []):
                # Determine if this item came from warmup (has original_filename or description)
                is_warmup = "original_filename" in item or "description" in item
                if pass_warmup != is_warmup:
                    continue
                media_hash = item.get("media_hash") or item.get("media_name", "")
                if not media_hash:
                    continue
                norm = _normalize_hash(media_hash)
                if norm not in records:
                    records[norm] = {}
                rec = records[norm]
                # Fill fields from this item only if not already set (first-write wins)
                if "title" not in rec and item.get("title"):
                    rec["title"] = item["title"]
                if "description" not in rec and item.get("description"):
                    rec["description"] = item["description"]
                if "original_filename" not in rec and item.get("original_filename"):
                    rec["original_filename"] = item["original_filename"]
                # Always store the canonical hash form
                if "media_hash" not in rec:
                    rec["media_hash"] = media_hash
    return records


def build_title_index(artworks: dict[str, dict]) -> dict[str, list[str]]:
    """Build normalized-title → [slug, ...] index for fuzzy matching.

    Each slug appears at most once per normalized key (deduplicated).
    Keys include the normalized repo title and the slug-as-words form.
    """
    index: dict[str, set[str]] = {}
    for slug, aw in artworks.items():
        norm = _normalize_for_match(aw.get("title", ""))
        if norm:
            index.setdefault(norm, set()).add(slug)
        slug_as_title = slug.replace("-", " ")
        index.setdefault(slug_as_title, set()).add(slug)
    return {k: list(v) for k, v in index.items()}


def load_rename_map() -> dict[str, str]:
    """Build old_slug -> new_slug from the cfdae9c rename commit."""
    result = subprocess.run(
        ["git", "show", "cfdae9c", "--name-status"],
        capture_output=True,
        text=True,
    )
    rename_map: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("R"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        _, old_path, new_path = parts
        if not old_path.startswith("_artworks/"):
            continue
        old_slug = Path(old_path).stem
        new_slug = Path(new_path).stem
        rename_map[old_slug] = new_slug
    return rename_map


def load_artworks() -> dict[str, dict]:
    """Return {slug: {title, image, description, galleries}} for all artworks."""
    artworks: dict[str, dict] = {}
    for path in ARTWORKS_DIR.glob("*.md"):
        slug = path.stem
        content = path.read_text(encoding="utf-8")
        fm_m = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_m:
            continue
        try:
            fm = yaml.safe_load(fm_m.group(1))
        except yaml.YAMLError:
            continue
        artworks[slug] = {
            "title": fm.get("title", ""),
            "image": fm.get("image", ""),
            "description": fm.get("description", ""),
            "galleries": fm.get("galleries", []),
        }
    return artworks


def load_gallery_order(gallery_id: str) -> list[str]:
    """Return ordered slug list for a gallery data file."""
    path = GALLERIES_DIR / f"{gallery_id}.yml"
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    return [
        line.strip()[2:].strip()
        for line in content.splitlines()
        if line.strip().startswith("- ")
    ]


def load_inventory() -> dict[str, dict]:
    """Parse _reports/archive_inventory.yml into a dict keyed by page slug."""
    with open(INVENTORY_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw or {}


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _try_slug(
    slug: str,
    rename_map: dict[str, str],
    artworks: dict[str, dict],
) -> str | None:
    """Return current slug if slug or its renamed version is in artworks."""
    for candidate in (slug, rename_map.get(slug)):
        if candidate and candidate in artworks:
            return candidate
    return None


def match_item(
    item: dict,
    rename_map: dict[str, str],
    artworks: dict[str, dict],
    title_index: dict[str, list[str]],
    gallery_filter: str | None = None,
) -> str | None:
    """Return the best current slug for an archive item, or None.

    Tries (in order):
    1. slugify(wix_title)            — exact slug match on display title
    2. slugify(original_filename)    — with and without extension; gallery-filtered
    3. fuzzy title match             — normalized title → title_index; unique matches only
    """
    orig_fn = item.get("original_filename", "")
    wix_title = item.get("title", "")

    # 1. Exact title slug match — semantically unambiguous, no gallery filter needed
    if wix_title:
        result = _try_slug(slugify(wix_title), rename_map, artworks)
        if result:
            return result

    # 2. Filename slug matches — apply gallery filter to avoid camera-filename collisions
    if orig_fn:
        for fn_slug in (slugify(orig_fn), slugify(orig_fn.rsplit(".", 1)[0])):
            result = _try_slug(fn_slug, rename_map, artworks)
            if result:
                if gallery_filter is None:
                    return result
                aw_galleries = artworks[result].get("galleries", [])
                mapped_galleries = set(GALLERY_MAP.values()) - {None}
                if (gallery_filter in aw_galleries
                        or not any(g in mapped_galleries for g in aw_galleries)):
                    return result

    # 3. Fuzzy title match — normalize and look up in title_index; unique only
    if wix_title:
        norm = _normalize_for_match(wix_title)
        if norm and norm in title_index:
            candidates = title_index[norm]
            if len(candidates) == 1:
                return candidates[0]

    return None


# ---------------------------------------------------------------------------
# YAML output helpers (no external dep)
# ---------------------------------------------------------------------------

def _yaml_str(s: str) -> str:
    if not s:
        return "''"
    needs_quote = any(c in s for c in ':#{}&*!,[]|>\n') or s[0] in "-?'"
    if needs_quote or '"' in s:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-order", action="store_true",
                        help="Rewrite gallery data files to archive order (not yet implemented)")
    args = parser.parse_args()

    rename_map = load_rename_map()
    artworks = load_artworks()
    inventory = load_inventory()

    print(f"Loaded {len(rename_map)} rename entries, {len(artworks)} artworks, "
          f"{len(inventory)} archive pages")

    # --- Build cross-page indexes ---
    hash_index = build_hash_index(inventory)
    title_index = build_title_index(artworks)
    print(f"Hash index: {len(hash_index)} distinct media hashes")

    # --- Per-item matching ---
    # Enrich each item with cross-page hash metadata before matching
    add_description: list[dict] = []
    description_conflicts: list[dict] = []
    title_conflicts: list[dict] = []
    unmatched_archive: list[dict] = []

    # Track which archive items claimed each slug (for duplicate detection)
    matched_slugs: dict[str, list] = {}

    for page_slug, page_data in inventory.items():
        items = page_data.get("items", [])
        if not items:
            continue
        gallery_filter = GALLERY_MAP.get(page_slug)
        for item in items:
            # Enrich item with cross-page hash metadata
            media_hash = item.get("media_hash") or item.get("media_name", "")
            norm = _normalize_hash(media_hash) if media_hash else ""
            hash_meta = hash_index.get(norm, {}) if norm else {}

            # Build enriched item: item fields take priority, hash_meta fills gaps
            enriched = dict(item)
            if not enriched.get("title") and hash_meta.get("title"):
                enriched["title"] = hash_meta["title"]
            if not enriched.get("description") and hash_meta.get("description"):
                enriched["description"] = hash_meta["description"]
            if not enriched.get("original_filename") and hash_meta.get("original_filename"):
                enriched["original_filename"] = hash_meta["original_filename"]

            current_slug = match_item(enriched, rename_map, artworks, title_index, gallery_filter)
            if current_slug is None:
                unmatched_archive.append({
                    "page": page_slug,
                    "original_filename": enriched.get("original_filename", ""),
                    "media_hash": enriched.get("media_hash", ""),
                    "title": enriched.get("title", ""),
                })
                continue

            matched_slugs.setdefault(current_slug, []).append(page_slug)
            artwork = artworks[current_slug]

            # Description: compare archive desc (from enriched) to existing artwork desc
            archive_desc = enriched.get("description", "")
            repo_desc = artwork.get("description", "")
            if archive_desc:
                if not repo_desc:
                    add_description.append({
                        "slug": current_slug,
                        "description": archive_desc,
                        "source_page": page_slug,
                    })
                elif repo_desc != archive_desc:
                    description_conflicts.append({
                        "slug": current_slug,
                        "repo_description": repo_desc,
                        "archive_description": archive_desc,
                        "source_page": page_slug,
                    })

            # Title conflict
            archive_title = normalize_title(enriched.get("title", ""))
            repo_title = normalize_title(artwork.get("title", ""))
            if archive_title and repo_title and archive_title != repo_title:
                title_conflicts.append({
                    "slug": current_slug,
                    "repo_title": artwork["title"],
                    "wix_title": enriched.get("title", ""),
                    "source_page": page_slug,
                })

    # Deduplicate add_description: keep one entry per slug (first encountered)
    desc_by_slug: dict[str, dict] = {}
    for entry in add_description:
        slug = entry["slug"]
        if slug not in desc_by_slug:
            desc_by_slug[slug] = entry

    # Deduplicate description_conflicts: keep one per slug
    desc_conflict_by_slug: dict[str, dict] = {}
    for entry in description_conflicts:
        slug = entry["slug"]
        if slug not in desc_conflict_by_slug:
            desc_conflict_by_slug[slug] = entry

    # Deduplicate title_conflicts: keep one per slug
    title_by_slug: dict[str, dict] = {}
    for entry in title_conflicts:
        slug = entry["slug"]
        if slug not in title_by_slug:
            title_by_slug[slug] = entry

    # --- Gallery order/membership (for mapped pages only) ---
    order_mismatches: list[dict] = []
    membership_mismatches: list[dict] = []

    for page_slug, gallery_id in GALLERY_MAP.items():
        if gallery_id is None:
            continue
        page_data = inventory.get(page_slug, {})
        archive_items = page_data.get("items", [])
        if not archive_items:
            continue

        repo_order = load_gallery_order(gallery_id)
        archive_order = []
        for item in archive_items:
            slug = match_item(item, rename_map, artworks, title_index, gallery_id)
            if slug:
                archive_order.append(slug)

        archive_set = set(archive_order)
        repo_set = set(repo_order)

        in_archive_not_repo = sorted(archive_set - repo_set)
        in_repo_not_archive = sorted(repo_set - archive_set)

        if in_archive_not_repo or in_repo_not_archive:
            membership_mismatches.append({
                "gallery": gallery_id,
                "archive_page": page_slug,
                "in_archive_not_repo": in_archive_not_repo,
                "in_repo_not_archive": in_repo_not_archive,
            })

        if archive_order != repo_order and archive_set == repo_set:
            order_mismatches.append({
                "gallery": gallery_id,
                "archive_page": page_slug,
                "archive_order": archive_order,
                "repo_order": repo_order,
            })

    # --- Fix gallery order ---
    if args.fix_order:
        # Collect archive items per gallery (multiple archive pages may share one gallery)
        gallery_archive_items: dict[str, list] = {}
        for page_slug, gallery_id in GALLERY_MAP.items():
            if gallery_id is None:
                continue
            page_data = inventory.get(page_slug, {})
            items = sorted(
                page_data.get("items", []),
                key=lambda x: x.get("order_index", 9999),
            )
            if items:
                gallery_archive_items.setdefault(gallery_id, []).extend(items)

        updated = 0
        for gallery_id, archive_items in gallery_archive_items.items():
            repo_order = load_gallery_order(gallery_id)
            if not repo_order:
                continue

            # Build archive-ordered slug list (deduplicated, skip unmatched)
            seen: set[str] = set()
            archive_order: list[str] = []
            for item in archive_items:
                slug = match_item(item, rename_map, artworks, title_index, gallery_id)
                if slug and slug not in seen:
                    archive_order.append(slug)
                    seen.add(slug)

            # Append repo-only items in their original relative order
            for slug in repo_order:
                if slug not in seen:
                    archive_order.append(slug)
                    seen.add(slug)

            if archive_order == repo_order:
                continue

            path = GALLERIES_DIR / f"{gallery_id}.yml"
            with open(path, "w", encoding="utf-8") as f:
                for slug in archive_order:
                    f.write(f"- {slug}\n")
            print(f"  Updated order: {gallery_id} ({len(archive_order)} slugs)")
            updated += 1

        print(f"\nUpdated {updated} gallery data files")

    # --- Unmatched repo artworks ---
    matched_set = set(matched_slugs.keys())
    unmatched_repo = sorted(set(artworks.keys()) - matched_set)

    # --- Summary ---
    print(f"\nResults:")
    print(f"  add_description:       {len(desc_by_slug)} artworks")
    print(f"  description_conflicts: {len(desc_conflict_by_slug)} artworks")
    print(f"  title_conflicts:       {len(title_by_slug)} artworks")
    print(f"  order_mismatches:      {len(order_mismatches)} galleries")
    print(f"  membership_mismatches: {len(membership_mismatches)} galleries")
    print(f"  unmatched_archive:     {len(unmatched_archive)} items")
    print(f"  unmatched_repo:        {len(unmatched_repo)} artworks")

    # --- Write YAML ---
    with open(RECONCILIATION_FILE, "w", encoding="utf-8") as f:
        f.write("# Archive reconciliation — generated by reconcile_archive_metadata.py\n\n")

        f.write(f"# {len(desc_by_slug)} artworks need a description added\n")
        f.write("add_description:\n")
        for slug, entry in sorted(desc_by_slug.items()):
            f.write(f"  {slug}:\n")
            f.write(f"    description: {_yaml_str(entry['description'])}\n")
            f.write(f"    source_page: {entry['source_page']}\n")

        f.write(f"\n# {len(desc_conflict_by_slug)} artworks with differing archive description\n")
        f.write("description_conflicts:\n")
        for slug, entry in sorted(desc_conflict_by_slug.items()):
            f.write(f"  {slug}:\n")
            f.write(f"    repo_description: {_yaml_str(entry['repo_description'])}\n")
            f.write(f"    archive_description: {_yaml_str(entry['archive_description'])}\n")
            f.write(f"    source_page: {entry['source_page']}\n")

        f.write(f"\n# {len(title_by_slug)} title conflicts (wix_title vs repo_title)\n")
        f.write("title_conflicts:\n")
        for slug, entry in sorted(title_by_slug.items()):
            f.write(f"  {slug}:\n")
            f.write(f"    repo_title: {_yaml_str(entry['repo_title'])}\n")
            f.write(f"    wix_title: {_yaml_str(entry['wix_title'])}\n")
            f.write(f"    source_page: {entry['source_page']}\n")

        f.write(f"\n# {len(order_mismatches)} gallery order mismatches\n")
        f.write("order_mismatches:\n")
        for entry in order_mismatches:
            f.write(f"  - gallery: {entry['gallery']}\n")
            f.write(f"    archive_page: {entry['archive_page']}\n")
            f.write(f"    archive_order: [{', '.join(entry['archive_order'])}]\n")
            f.write(f"    repo_order: [{', '.join(entry['repo_order'])}]\n")

        f.write(f"\n# {len(membership_mismatches)} gallery membership mismatches\n")
        f.write("membership_mismatches:\n")
        for entry in membership_mismatches:
            f.write(f"  - gallery: {entry['gallery']}\n")
            f.write(f"    archive_page: {entry['archive_page']}\n")
            if entry["in_archive_not_repo"]:
                items_str = "\n".join(f"      - {s}" for s in entry["in_archive_not_repo"])
                f.write(f"    in_archive_not_repo:\n{items_str}\n")
            if entry["in_repo_not_archive"]:
                items_str = "\n".join(f"      - {s}" for s in entry["in_repo_not_archive"])
                f.write(f"    in_repo_not_archive:\n{items_str}\n")

        f.write(f"\n# {len(unmatched_archive)} archive items with no repo match\n")
        f.write("unmatched_archive_items:\n")
        for item in unmatched_archive:
            f.write(f"  - page: {item['page']}\n")
            if item["original_filename"]:
                f.write(f"    original_filename: {_yaml_str(item['original_filename'])}\n")
            if item["media_hash"]:
                f.write(f"    media_hash: {_yaml_str(item['media_hash'])}\n")
            if item["title"]:
                f.write(f"    title: {_yaml_str(item['title'])}\n")

        f.write(f"\n# {len(unmatched_repo)} repo artworks not found in any archive page\n")
        f.write("unmatched_repo_artworks:\n")
        for slug in unmatched_repo:
            f.write(f"  - {slug}\n")

    print(f"\nWrote {RECONCILIATION_FILE}")


if __name__ == "__main__":
    main()
