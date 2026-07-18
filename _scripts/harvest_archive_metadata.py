#!/usr/bin/env python3
"""Download and parse Wayback Machine captures of hfgudeart.com.

Writes:
    _reports/archive_pages/<slug>.html  (cached raw HTML)
    _reports/archive_inventory.yml      (parsed metadata, keyed by slug)

Usage:
    uv run python3 _scripts/harvest_archive_metadata.py [--force] [--slug SLUG]
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Page list: slug -> preferred Wayback timestamp
# ---------------------------------------------------------------------------

PAGES = {
    "/": "20230511070157",
    "/about2": "20230511080454",
    "/cal-campus": "20230511070941",
    "/cal-men-s-rowing": "20230511073644",
    "/contact": "20230511075803",
    "/copy-of-artist-bio": "20210516073950",
    "/copy-of-berkeley-campus": "20230511073921",
    "/copy-of-cal-marching-band": "20230511080720",
    "/copy-of-cal-marching-band-1": "20230511073802",
    "/copy-of-cal-men-s-rowing": "20230511080035",
    "/copy-of-campus-drawings": "20230511080606",
    "/copy-of-campus-paintings": "20230511081002",
    "/copy-of-campus-paintings-1": "20230511074652",
    "/copy-of-figure-drawings": "20230511075213",
    "/copy-of-figure-drawings-complete-fi": "20230511074045",
    "/copy-of-figures": "20230511080317",
    "/copy-of-figures-1": "20230511070629",
    "/copy-of-finished-drawings": "20230511081229",
    "/copy-of-finished-drawings-1": "20230511075403",
    "/copy-of-home": "20230510073321",
    "/copy-of-landscapes": "20230511072346",
    "/copy-of-landscapes-1": "20230511074408",
    "/copy-of-new-page": "20230511072458",
    "/copy-of-other-landscapes": "20230511081344",
    "/copy-of-rowing-drawings": "20230511081647",
    "/copy-of-rowing-drawings-1": "20230510071710",
    "/copy-of-rowing-drawings-2": "20230511071617",
    "/copy-of-select-charcoal-drawings": "20230510072040",
    "/copy-of-select-watercolors-gouache": "20230511075916",
    "/copy-of-sketches-studies": "20230511075526",
    "/copy-of-the-play-drawings": "20230511073527",
    "/copy-of-watercolor-gouache": "20230511072918",
    "/drawings": "20230511080153",
    "/drawings-finished-drawings": "20230511070421",
    "/drawings-sketches-studies": "20230511072207",
    "/emily": "20230511071226",
    "/figures": "20230511071835",
    "/figures-figure-studies": "20230510073621",
    "/figures-life-drawing-class": "20230509081140",
    "/figures-paintings": "20230511072054",
    "/images-of-cal-marching-band": "20230511072725",
    "/images-of-cal-sports": "20230511070827",
    "/images-of-the-berkeley-campus": "20230511074245",
    "/in-progress": "20230511073407",
    "/landscapes": "20230511075639",
    "/landscapes-mt-diablo": "20230511081533",
    "/landscapes-other": "20230511072611",
    "/landscapes-outdoors": "20230511073137",
    "/landscapes-watercolor-g": "20230510071001",
    "/new-drawing-class-offered": "20220831074353",
    "/old-versions-of-pages": "20230511081117",
    "/photographs": "20230511075056",
    "/still-lifes": "20230510071336",
    "/uc-berkeley-artworks": "20230511074936",
    # Dropped from 2023 sitemap but still archived:
    "/cal-branded-artwork": "20210513071145",
    "/hfgudeart": "20220531070422",
}

BASE_SITE = "https://www.hfgudeart.com"
REPORTS_DIR = Path("_reports")
PAGES_DIR = REPORTS_DIR / "archive_pages"
INVENTORY_FILE = REPORTS_DIR / "archive_inventory.yml"

# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------


def slug_to_filename(slug: str) -> str:
    """Convert a URL slug to a safe filename."""
    safe = slug.lstrip("/").replace("/", "_") or "index"
    return f"{safe}.html"


def wayback_url(timestamp: str, site_slug: str) -> str:
    url_path = BASE_SITE + site_slug
    return f"https://web.archive.org/web/{timestamp}id_/{url_path}"


def fetch_page(url: str) -> bytes | None:
    """Fetch a URL using curl; return raw bytes or None on error."""
    result = subprocess.run(
        ["curl", "-sL", "--compressed", "--max-time", "30", url],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def cdx_earlier_timestamps(site_slug: str) -> list[str]:
    """Return earlier 200-status timestamps for a slug, newest first."""
    cdx_url = (
        "http://web.archive.org/cdx/search/cdx"
        f"?url=hfgudeart.com{site_slug}"
        "&output=text&fl=timestamp,statuscode&filter=statuscode:200"
        "&collapse=timestamp:8&limit=20"
    )
    result = subprocess.run(
        ["curl", "-s", "--max-time", "20", cdx_url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    timestamps = []
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 1:
            timestamps.append(parts[0])
    # newest first, skip the preferred one (handled by caller)
    return list(reversed(timestamps))


def download_page(slug: str, timestamp: str, cache_path: Path, force: bool) -> str | None:
    """Download and cache a page; return HTML string or None."""
    if cache_path.exists() and not force:
        html = cache_path.read_text(encoding="utf-8", errors="replace")
        if "wix-warmup-data" in html:
            return html
        # Cached file is a JS shell; fall through to re-download

    url = wayback_url(timestamp, slug)
    print(f"  Fetching {url}", flush=True)
    raw = fetch_page(url)
    if raw is None:
        print(f"  ERROR: curl failed for {slug}", file=sys.stderr)
        return None

    html = raw.decode("utf-8", errors="replace")
    if "wix-warmup-data" not in html:
        print(f"  JS shell detected for {slug}; querying CDX for fallback", flush=True)
        earlier = cdx_earlier_timestamps(slug)
        for ts in earlier:
            if ts == timestamp:
                continue
            time.sleep(2)
            url2 = wayback_url(ts, slug)
            print(f"  Trying {url2}", flush=True)
            raw2 = fetch_page(url2)
            if raw2 is None:
                continue
            html2 = raw2.decode("utf-8", errors="replace")
            if "wix-warmup-data" in html2:
                html = html2
                print(f"  Found warmup data at timestamp {ts}", flush=True)
                break
        else:
            print(f"  WARNING: no warmup data found for {slug}", file=sys.stderr)

    cache_path.write_text(html, encoding="utf-8")
    return html


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# WIX pro-gallery app UUID (constant across all hfgudeart.com pages)
_PROGALLERY_APP_ID = "14271d6f-ba62-d045-549b-ab972ae1f70e"

# Captures the base media hash without the size suffix: f11310_<hex>~mv2
_MEDIA_HASH_RE = re.compile(r"(f11310_[0-9a-f]+~mv2)", re.IGNORECASE)
# Dimension infix from WIX media filename: _d_W_H_
_DIM_RE = re.compile(r"_d_(\d+)_(\d+)_")


def _extract_media_hash(name: str) -> str | None:
    m = _MEDIA_HASH_RE.search(name)
    return m.group(1) if m else None


def _extract_dimensions(name: str) -> tuple[int, int] | None:
    m = _DIM_RE.search(name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    # Normalize curly quotes to straight quotes for later comparison
    s = s.replace("'", "'").replace("'", "'")
    s = s.replace(""", '"').replace(""", '"')
    return s


def parse_warmup_data(html: str) -> tuple[dict, str | None]:
    """Return (warmup_data_dict, page_title). warmup_data_dict may be empty."""
    m = re.search(
        r'<script[^>]*id=["\']wix-warmup-data["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return {}, None

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"  WARNING: JSON parse error in warmup data: {e}", file=sys.stderr)
        return {}, None

    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    page_title = title_m.group(1).strip() if title_m else None
    if page_title:
        page_title = re.sub(r"\s+", " ", page_title)

    return data, page_title


def extract_gallery_items(warmup: dict) -> list[dict]:
    """Extract gallery items sorted by orderIndex from the WIX warmup blob.

    Structure:
        warmup['appsWarmupData'][PROGALLERY_APP_ID]['<comp-id>_galleryData']['items']

    Each item has:
        mediaUrl: str          — WIX media filename (f11310_<hash>~mv2_d_W_H_...)
        orderIndex: float      — display order
        metaData.title: str
        metaData.description: str
        metaData.fileName: str — original upload filename (IMG_0032a.jpg)
        metaData.width/height: int
    """
    app_data = warmup.get("appsWarmupData", {}).get(_PROGALLERY_APP_ID)
    if not isinstance(app_data, dict):
        return []

    all_items: list[dict] = []
    seen_hashes: set[str] = set()

    for key, value in app_data.items():
        if not key.endswith("_galleryData"):
            continue
        if not isinstance(value, dict):
            continue
        raw_items = value.get("items", [])
        if not isinstance(raw_items, list):
            continue

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            media_name = raw.get("mediaUrl", "")
            meta = raw.get("metaData", {}) if isinstance(raw.get("metaData"), dict) else {}

            hash_ = _extract_media_hash(media_name)
            key_id = hash_ or media_name
            if not key_id or key_id in seen_hashes:
                continue
            seen_hashes.add(key_id)

            # Dimensions: prefer metaData values (authoritative), fall back to filename
            w = meta.get("width") or 0
            h = meta.get("height") or 0
            if not (w and h):
                dims = _extract_dimensions(media_name)
                if dims:
                    w, h = dims

            orig_filename = meta.get("fileName", "")
            title = _clean_text(meta.get("title") or "")
            desc = _clean_text(meta.get("description") or "")
            order = raw.get("orderIndex", 0)

            item: dict = {
                "order_index": order,
                "media_name": media_name,
            }
            if hash_:
                item["media_hash"] = hash_
            if orig_filename:
                item["original_filename"] = orig_filename
            if w and h:
                item["width"] = int(w)
                item["height"] = int(h)
            if title:
                item["title"] = title
            if desc:
                item["description"] = desc
            all_items.append(item)

    all_items.sort(key=lambda x: x["order_index"])
    # Replace float order_index with stable integer position (1-based)
    for i, item in enumerate(all_items):
        item["order_index"] = i + 1

    return all_items


def extract_page_text(html: str) -> list[str]:
    """Extract rich-text blocks (non-gallery prose) stripped to plain text."""
    # Look for rich-text blocks commonly used for page intro/descriptions
    blocks = []
    for m in re.finditer(
        r'<(?:p|h[1-6])[^>]*class="[^"]*(?:font_[0-9]|richText)[^"]*"[^>]*>(.*?)</(?:p|h[1-6])>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = _clean_text(text)
        if text and len(text) > 10:
            blocks.append(text)
    return blocks


# ---------------------------------------------------------------------------
# YAML output helpers (no external dep)
# ---------------------------------------------------------------------------

def _yaml_str(s: str) -> str:
    """Emit a YAML scalar, quoting if necessary."""
    if not s:
        return "''"
    needs_quote = any(c in s for c in ':#{}&*!,[]|>"\'\n') or s[0] in "-? "
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _emit_item(item: dict, indent: int = 4) -> list[str]:
    pad = " " * indent
    lines = [f"{pad}- order_index: {item['order_index']}"]
    lines.append(f"{pad}  media_name: {_yaml_str(item['media_name'])}")
    if "media_hash" in item:
        lines.append(f"{pad}  media_hash: {_yaml_str(item['media_hash'])}")
    if "original_filename" in item:
        lines.append(f"{pad}  original_filename: {_yaml_str(item['original_filename'])}")
    if "width" in item:
        lines.append(f"{pad}  width: {item['width']}")
        lines.append(f"{pad}  height: {item['height']}")
    if "title" in item:
        lines.append(f"{pad}  title: {_yaml_str(item['title'])}")
    if "description" in item:
        lines.append(f"{pad}  description: {_yaml_str(item['description'])}")
    return lines


def write_inventory(inventory: dict[str, dict], path: Path) -> None:
    lines = ["# Archive inventory — generated by harvest_archive_metadata.py", ""]
    for slug, entry in sorted(inventory.items()):
        safe_slug = slug.lstrip("/") or "index"
        lines.append(f"{safe_slug}:")
        if entry.get("page_title"):
            lines.append(f"  page_title: {_yaml_str(entry['page_title'])}")
        items = entry.get("items", [])
        if items:
            lines.append(f"  item_count: {len(items)}")
            lines.append("  items:")
            for item in items:
                lines.extend(_emit_item(item))
        else:
            lines.append("  items: []")
        page_texts = entry.get("page_texts", [])
        if page_texts:
            lines.append("  page_texts:")
            for txt in page_texts:
                lines.append(f"    - {_yaml_str(txt)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    parser.add_argument("--slug", help="Process only this slug (e.g. /still-lifes)")
    args = parser.parse_args()

    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    pages_to_process = {args.slug: PAGES[args.slug]} if args.slug else PAGES

    # Load existing inventory so we can update incrementally
    inventory: dict[str, dict] = {}

    total_items = 0
    items_with_desc = 0

    for i, (slug, timestamp) in enumerate(pages_to_process.items()):
        safe = slug.lstrip("/") or "index"
        cache_path = PAGES_DIR / slug_to_filename(slug)
        print(f"[{i+1}/{len(pages_to_process)}] {slug}", flush=True)

        html = download_page(slug, timestamp, cache_path, args.force)
        if html is None:
            print(f"  SKIP: could not download {slug}", file=sys.stderr)
            continue

        warmup, page_title = parse_warmup_data(html)
        if not warmup:
            print(f"  No warmup data in {slug}")
        else:
            print(f"  Parsed warmup data OK")

        items = extract_gallery_items(warmup) if warmup else []
        page_texts = extract_page_text(html)

        print(f"  {len(items)} gallery items, {len(page_texts)} text blocks")
        for item in items:
            total_items += 1
            if item.get("description"):
                items_with_desc += 1

        entry: dict = {"items": items}
        if page_title:
            entry["page_title"] = page_title
        if page_texts:
            entry["page_texts"] = page_texts
        inventory[safe] = entry

        # Rate-limit between pages
        if i < len(pages_to_process) - 1:
            time.sleep(2)

    write_inventory(inventory, INVENTORY_FILE)
    print(f"\nWrote {INVENTORY_FILE}")
    print(f"Total gallery items: {total_items}")
    print(f"Items with description: {items_with_desc}")
    distinct_hashes: set[str] = set()
    for entry in inventory.values():
        for item in entry.get("items", []):
            h = item.get("media_hash") or item.get("media_name", "")
            if h:
                distinct_hashes.add(h)
    print(f"Distinct media hashes: {len(distinct_hashes)}")


if __name__ == "__main__":
    main()
