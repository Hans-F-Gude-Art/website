#!/usr/bin/env python3
"""Download and parse Wayback Machine captures of hfgudeart.com.

Understands two WIX gallery formats:
  - warmup: wix-warmup-data JSON (has descriptions; preferred)
  - SSR:    gallery-item-container divs (server-rendered; no descriptions)

Writes:
    _reports/archive_pages/<slug>.html              (primary cached HTML)
    _reports/archive_pages/<slug>.<ts>.html         (CDX fallback captures)
    _reports/archive_inventory.yml                  (parsed metadata)

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

# Pages that legitimately have zero gallery items.
NO_GALLERY_PAGES = {
    "about2", "contact", "copy-of-artist-bio", "copy-of-home",
    "hfgudeart", "index", "new-drawing-class-offered", "old-versions-of-pages",
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
    return list(reversed(timestamps))


def _has_gallery_content(html: str) -> bool:
    """Return True if the page has any parseable gallery items."""
    return (
        "gallery-item-container visible clickable" in html
        or "wix-warmup-data" in html
    )


def download_page(slug: str, timestamp: str, cache_path: Path, force: bool) -> str | None:
    """Download and cache a page; return HTML string or None.

    Falls back to CDX earlier captures if the primary timestamp is a JS shell
    (no gallery content from either warmup or SSR parsers).
    """
    if cache_path.exists() and not force:
        html = cache_path.read_text(encoding="utf-8", errors="replace")
        if _has_gallery_content(html):
            return html
        # Cached file has no gallery content; fall through to re-download

    url = wayback_url(timestamp, slug)
    print(f"  Fetching {url}", flush=True)
    raw = fetch_page(url)
    if raw is None:
        print(f"  ERROR: curl failed for {slug}", file=sys.stderr)
        return None

    html = raw.decode("utf-8", errors="replace")
    if not _has_gallery_content(html):
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
            if _has_gallery_content(html2):
                html = html2
                alt_path = cache_path.parent / (cache_path.stem + f".{ts}.html")
                alt_path.write_text(html2, encoding="utf-8")
                print(f"  Found gallery content at timestamp {ts}", flush=True)
                break
        else:
            print(f"  WARNING: no gallery content found for {slug}", file=sys.stderr)

    cache_path.write_text(html, encoding="utf-8")
    return html


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# WIX pro-gallery app UUID (constant across all hfgudeart.com pages)
_PROGALLERY_APP_ID = "14271d6f-ba62-d045-549b-ab972ae1f70e"

# Captures the base media hash; both ~mv2 and plain forms.
# f11310_326a2ba6f6de4887b08a62cc294851cf~mv2 OR f11310_58af11b7794a4a2890a893ee1e75ae2a
_MEDIA_HASH_RE = re.compile(r"(f11310_[0-9a-f]+(?:~mv2)?)", re.IGNORECASE)
# Dimension infix from WIX media filename: _d_W_H_
_DIM_RE = re.compile(r"_d_(\d+)_(\d+)_")

# SSR gallery container: aria-label holds title, data-id holds UUID
_SSR_CONTAINER_RE = re.compile(
    r'<div[^>]*class="[^"]*gallery-item-container[^"]*"[^>]*'
    r'id="(pgi[^"]+)"[^>]*'
    r'aria-label="([^"]*)"[^>]*'
    r'data-id="([^"]+)"',
    re.IGNORECASE,
)
# item-wrapper holds the picture element with srcSet
_SSR_WRAPPER_RE = re.compile(
    r'id="item-wrapper-([^"]+)".*?srcSet="([^"]+)"',
    re.IGNORECASE | re.DOTALL,
)


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
    s = s.replace("‘", "'").replace("’", "'")
    s = s.replace("“", '"').replace("”", '"')
    return s


def _normalize_hash(h: str) -> str:
    """Return lowercase f11310_<hex> without ~mv2 for deduplication."""
    m = re.match(r"f11310_([0-9a-f]+)", h, re.IGNORECASE)
    return f"f11310_{m.group(1).lower()}" if m else h.lower()


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


def extract_warmup_items(warmup: dict) -> list[dict]:
    """Extract gallery items sorted by orderIndex from the WIX warmup blob.

    Structure:
        warmup['appsWarmupData'][PROGALLERY_APP_ID]['<comp-id>_galleryData']['items']
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
            norm = _normalize_hash(hash_ or media_name)
            if not norm or norm in seen_hashes:
                continue
            seen_hashes.add(norm)

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
                "_norm_hash": norm,
                "_source": "warmup",
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
    for i, item in enumerate(all_items):
        item["order_index"] = i + 1

    return all_items


def extract_ssr_items(html: str) -> list[dict]:
    """Parse SSR pro-gallery items from gallery-item-container markup.

    Container:
        <div class="gallery-item-container visible clickable"
             id="pgi{uuid_no_dashes}_{idx}"
             aria-label="{title}"
             data-id="{uuid}">

    Media URL is inside id="item-wrapper-{uuid}" → <source srcSet="...f11310_<hash>...">.
    Title 'untitled image' (case-insensitive) is treated as blank.
    Order = the _{idx} numeric suffix in the container id (0-based).
    """
    # Build a UUID → (f11310_hash) lookup from all item-wrappers
    wrapper_hash: dict[str, str] = {}
    for wm in _SSR_WRAPPER_RE.finditer(html):
        uuid = wm.group(1)
        srcset = wm.group(2)
        hm = _MEDIA_HASH_RE.search(srcset)
        if hm:
            wrapper_hash[uuid] = hm.group(1)

    items: list[dict] = []
    seen_hashes: set[str] = set()

    for cm in _SSR_CONTAINER_RE.finditer(html):
        container_id = cm.group(1)
        aria_label = cm.group(2).strip()
        uuid = cm.group(3)

        # Order from trailing _N in container id
        order_m = re.search(r"_(\d+)$", container_id)
        order = int(order_m.group(1)) if order_m else len(items)

        title = ""
        if aria_label and aria_label.lower() != "untitled image":
            title = _clean_text(aria_label)

        media_hash = wrapper_hash.get(uuid, "")
        if not media_hash:
            continue
        norm = _normalize_hash(media_hash)
        if norm in seen_hashes:
            continue
        seen_hashes.add(norm)

        item: dict = {
            "order_index": order,
            "media_name": media_hash,
            "media_hash": media_hash,
            "_norm_hash": norm,
            "_source": "ssr",
        }
        if title:
            item["title"] = title
        items.append(item)

    items.sort(key=lambda x: x["order_index"])
    for i, item in enumerate(items):
        item["order_index"] = i + 1

    return items


def merge_gallery_items(warmup_items: list[dict], ssr_items: list[dict]) -> list[dict]:
    """Merge warmup and SSR items; warmup wins on hash collision.

    Resulting list: warmup items first (in warmup order), then SSR items
    whose hashes don't appear in warmup (in SSR order).
    """
    warmup_hashes = {item["_norm_hash"] for item in warmup_items}
    extra_ssr = [item for item in ssr_items if item["_norm_hash"] not in warmup_hashes]

    merged = list(warmup_items) + extra_ssr
    # Re-number order_index sequentially
    for i, item in enumerate(merged):
        item["order_index"] = i + 1
    return merged


def _strip_internal(items: list[dict]) -> list[dict]:
    """Remove internal-only keys (_norm_hash, _source) before writing inventory."""
    result = []
    for item in items:
        clean = {k: v for k, v in item.items() if not k.startswith("_")}
        result.append(clean)
    return result


def extract_page_text(html: str) -> list[str]:
    """Extract rich-text blocks (non-gallery prose) stripped to plain text."""
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
        if entry.get("no_items_reason"):
            lines.append(f"  no_items_reason: {_yaml_str(entry['no_items_reason'])}")
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
        warmup_items = extract_warmup_items(warmup) if warmup else []
        ssr_items = extract_ssr_items(html)
        items = merge_gallery_items(warmup_items, ssr_items)

        warmup_count = len(warmup_items)
        ssr_new = len(items) - len(warmup_items)
        print(
            f"  {len(items)} items (warmup={warmup_count}, ssr_new={ssr_new})",
            flush=True,
        )

        # Second-chance CDX fallback: page still has 0 items after both parsers
        no_items_reason: str | None = None
        if not items and safe not in NO_GALLERY_PAGES:
            print(f"  0 items after both parsers; trying CDX fallback", flush=True)
            earlier = cdx_earlier_timestamps(slug)
            found = False
            for ts in earlier:
                if ts == timestamp:
                    continue
                alt_path = cache_path.parent / (cache_path.stem + f".{ts}.html")
                if alt_path.exists() and not args.force:
                    alt_html = alt_path.read_text(encoding="utf-8", errors="replace")
                else:
                    time.sleep(2)
                    url2 = wayback_url(ts, slug)
                    print(f"  Trying {url2}", flush=True)
                    raw2 = fetch_page(url2)
                    if raw2 is None:
                        continue
                    alt_html = raw2.decode("utf-8", errors="replace")
                    alt_path.write_text(alt_html, encoding="utf-8")

                w2, _ = parse_warmup_data(alt_html)
                wi2 = extract_warmup_items(w2) if w2 else []
                si2 = extract_ssr_items(alt_html)
                merged2 = merge_gallery_items(wi2, si2)
                if merged2:
                    items = merged2
                    html = alt_html
                    print(
                        f"  Found {len(items)} items at {ts} "
                        f"(warmup={len(wi2)}, ssr_new={len(merged2)-len(wi2)})",
                        flush=True,
                    )
                    found = True
                    break

            if not found:
                no_items_reason = "no gallery content in any capture"
                print(f"  WARNING: {no_items_reason} for {slug}", file=sys.stderr)

        page_texts = extract_page_text(html)

        for item in items:
            total_items += 1
            if item.get("description"):
                items_with_desc += 1

        entry: dict = {"items": _strip_internal(items)}
        if page_title:
            entry["page_title"] = page_title
        if no_items_reason:
            entry["no_items_reason"] = no_items_reason
        if page_texts:
            entry["page_texts"] = page_texts
        inventory[safe] = entry

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
                distinct_hashes.add(_normalize_hash(h))
    print(f"Distinct media hashes: {len(distinct_hashes)}")


if __name__ == "__main__":
    main()
