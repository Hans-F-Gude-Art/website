#!/usr/bin/env python3
"""Measure every image slot in the built site and check its responsive sizes.

Loads sample pages from `_site/` in headless Chromium at each CSS breakpoint
and at 1x, 2x, and 3x pixel density, and records three widths per image:

- slot: the CSS pixels the layout gives the image;
- declared: the width its `sizes` attribute claims (eager images only;
  `sizes="auto, ..."` uses the slot width);
- delivered: the width of the file the browser chose (`currentSrc`).

A slot is the CSS context an image sits in, named by the image's id or
class, or by its nearest ancestor with a class (`.photo-grid img`).
Every image in a slot is sized by the same CSS rule, so the check loads a
fixed sample of pages (SAMPLE_PAGES) plus artwork pages chosen for their
image shape: the artwork image is limited by both width and height, so
portrait, square, and landscape images fill different slot widths.

Images with `srcset` fail the check when:

- `sizes` understates the slot (the browser may pick a blurry copy) or
  overstates it by more than SIZES_SLACK (it may pick a needlessly large one);
- the delivered file is narrower than the slot at min(DPR, 2) and the
  source is wider (a wider candidate exists or could be generated);
- the delivered file is more than WASTE_FACTOR times the slot at the DPR;
- a `srcset` width descriptor differs from the width of the file it names.

Delivered widths are read by decoding the file, never from the descriptor.

A slot found in the HTML but never visible at any viewport fails the
check, so no slot goes unmeasured.

Images without `srcset` and SVGs are reported, never failed. The report
lists each slot's width range and the widths a `srcset` for it would need.

It also fails when the Largest Contentful Paint element is an image with
`loading="lazy"`: a lazy image waits for layout, which delays the paint.
This is read at 1x on every sampled page.

Exit codes: 0 when every check passes, 1 when any fails, 2 on bad input.

Usage:
    uv run --group browser python ci/check_image_sizes.py ../_site
Example: ../_site
"""

from __future__ import annotations

import argparse
import asyncio
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

EXIT_CLEAN = 0
EXIT_FAILED = 1
EXIT_UNUSABLE = 2

REPO = Path(__file__).resolve().parents[2]
# Breakpoints are read from the stylesheet's media queries and from the
# `sizes` media conditions in the layouts; each is tested one pixel below,
# at, and one pixel above its width, so every layout is measured.
BREAKPOINT_SOURCES = (REPO / "assets" / "css" / "style.scss", *sorted((REPO / "_layouts").glob("*.html")))
BREAKPOINT = re.compile(r"\((?:min|max)-width:\s*([\d.]+)em\)")
# The pages that hold every slot: the homepage and a hub (.gallery-grid),
# a curated and a medium gallery (.photo-grid), and the bio (.bio-figure).
SAMPLE_PAGES = ("/", "/human-figure/", "/human-figure/paintings/", "/by-medium/oils/", "/about/")
# Artwork pages per image shape: the most portrait, the closest to square,
# and the most landscape.
ARTWORKS_PER_SHAPE = 2
# Common phone, desktop, and wide screens, added to the breakpoint widths.
EXTRA_WIDTHS = (320, 390, 1280, 1920)
VIEWPORT_HEIGHT = 900
DPRS = (1, 2, 3)
# Above 2x the eye gains little for the bytes, so 3x screens need only 2x.
MAX_USEFUL_DPR = 2
# The widest copy ImageDerivatives makes is the largest `widths` value in
# _config.yml. A need above it is met at that width by design; the original
# is offered only when it is no wider than that.
CONFIG = REPO / "_config.yml"
WIDTHS = re.compile(r"^[\s-]*widths:\s*\[([\d,\s]+)\]", re.MULTILINE)
IMAGES_PER_SLOT = 3

TOLERANCE = 0.05
SIZES_SLACK = 1.1
WASTE_FACTOR = 2.0

SITE_ORIGIN = "https://site.test"
VOID_ELEMENTS = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    ]
)


@dataclass(frozen=True)
class Measurement:
    """One image on one page at one viewport width and pixel density."""

    page: str
    viewport: int
    dpr: int
    slot: str
    src: str
    slot_width: float
    declared: float | None
    has_srcset: bool
    vector: bool
    delivered: int
    widest_available: int
    # "<url> is <N>w, srcset says <M>w" for each descriptor that is wrong.
    mismatches: tuple[str, ...] = ()


@dataclass(frozen=True)
class LargestPaint:
    """The Largest Contentful Paint element of one page at one viewport width."""

    page: str
    viewport: int
    # ".artwork-full-size img /a.jpg", "h1", ...; None when the browser reported none.
    element: str | None
    lazy: bool


def max_copy_width(config: str) -> int | None:
    """Return the largest ImageDerivatives width in a config, or None when none."""
    widths = [int(w) for match in WIDTHS.findall(config) for w in match.split(",") if w.strip()]
    return max(widths, default=None)


def problems(m: Measurement, max_width: int | None = None) -> list[str]:
    """Return why this measurement fails the check; empty when it passes.

    `max_width` is the widest copy ImageDerivatives makes; no need above it
    fails.
    """
    if not m.has_srcset or m.vector or m.slot_width <= 0:
        return []

    found = [f"srcset descriptor is wrong: {mismatch}" for mismatch in m.mismatches]
    if m.declared is not None:
        if m.declared < m.slot_width * (1 - TOLERANCE):
            found.append(
                f"sizes declares {m.declared:.0f}px for a {m.slot_width:.0f}px slot (understated)"
            )
        elif m.declared > m.slot_width * SIZES_SLACK:
            found.append(
                f"sizes declares {m.declared:.0f}px for a {m.slot_width:.0f}px slot (overstated)"
            )

    need = m.slot_width * min(m.dpr, MAX_USEFUL_DPR)
    if max_width is not None:
        need = min(need, max_width)
    if m.delivered < need * (1 - TOLERANCE) and m.widest_available > m.delivered:
        found.append(
            f"delivered {m.delivered}w for a {need:.0f}px need; "
            f"the source is {m.widest_available}w, so a wider candidate is possible"
        )
    if m.delivered > m.slot_width * m.dpr * WASTE_FACTOR:
        found.append(
            f"delivered {m.delivered}w for a {m.slot_width * m.dpr:.0f}px slot "
            f"at {m.dpr}x (over {WASTE_FACTOR:g}x)"
        )
    return found


def viewport_widths(*sources: str) -> list[int]:
    """Return the widths to test: around each em breakpoint, plus extras."""
    widths = set(EXTRA_WIDTHS)
    for source in sources:
        for em in BREAKPOINT.findall(source):
            px = round(float(em) * 16)
            widths.update((px - 1, px, px + 1))
    return sorted(widths)


class _SlotScanner(HTMLParser):
    """Collect the slot key of every <img> in a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[list[str]] = []
        self.slots: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "img":
            self.slots.add(slot_key(values.get("id"), classes, reversed(self.stack)))
        elif tag not in VOID_ELEMENTS:
            self.stack.append(classes)

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID_ELEMENTS and self.stack:
            self.stack.pop()


def slot_key(img_id, img_classes, ancestor_classes) -> str:
    """Name an image's slot; must match SLOT_KEY_JS."""
    if img_id:
        return f"#{img_id}"
    if img_classes:
        return "img." + ".".join(img_classes)
    for depth, classes in enumerate(ancestor_classes):
        if depth >= 4:
            break
        if classes:
            return "." + ".".join(classes) + " img"
    return "img"


def page_file(site: Path, path: str) -> Path:
    """Return the index.html that serves a page path."""
    return site / path.strip("/") / "index.html"


class _ArtworkImage(HTMLParser):
    """Read the width and height of the artwork image on an artwork page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_link = False
        self.size: tuple[int, int] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "artwork-full-size" in (values.get("class") or "").split():
            self.in_link = True
        elif tag == "img" and self.in_link and self.size is None:
            self.size = (int(values.get("width") or 0), int(values.get("height") or 0))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.in_link = False


def artwork_pages(site: Path, per_shape: int = ARTWORKS_PER_SHAPE) -> list[str]:
    """Return artwork pages: the most portrait, closest to square, and most landscape."""
    ratios = []
    for file in sorted((site / "artwork").glob("*/index.html")):
        scanner = _ArtworkImage()
        scanner.feed(file.read_text(encoding="utf-8", errors="replace"))
        if scanner.size and all(scanner.size):
            width, height = scanner.size
            ratios.append((width / height, f"/artwork/{file.parent.name}/"))
    if not ratios:
        return []
    ratios.sort()
    square = sorted(ratios, key=lambda ratio: abs(math.log(ratio[0])))
    chosen = ratios[:per_shape] + square[:per_shape] + ratios[-per_shape:]
    return sorted({path for _, path in chosen})


def chosen_pages(site: Path) -> list[str]:
    """Return SAMPLE_PAGES that exist, then the artwork pages by shape."""
    fixed = [path for path in SAMPLE_PAGES if page_file(site, path).is_file()]
    return fixed + artwork_pages(site)


def sample_pages(site: Path, pages: list[str]) -> dict[str, list[str]]:
    """Return slot key -> the pages in `pages` that contain it."""
    sampled: dict[str, list[str]] = defaultdict(list)
    for path in pages:
        scanner = _SlotScanner()
        scanner.feed(page_file(site, path).read_text(encoding="utf-8", errors="replace"))
        for slot in sorted(scanner.slots):
            sampled[slot].append(path)
    return dict(sampled)


SLOT_KEY_JS = """
img => {
  if (img.id) return '#' + img.id;
  if (img.classList.length) return 'img.' + [...img.classList].join('.');
  let e = img.parentElement;
  for (let i = 0; i < 4 && e; i++, e = e.parentElement) {
    if (e.classList.length) return '.' + [...e.classList].join('.') + ' img';
  }
  return 'img';
}
"""

# Returns one measurement per image, resolving `sizes` the way the browser
# does: the first entry whose media condition matches, its length measured
# on a probe element. `auto` on a lazy image means the slot width.
MEASURE_JS = (
    """
(img) => {
  const slotKey = """
    + SLOT_KEY_JS
    + """;
  const candidates = (img.getAttribute('srcset') || '').split(',').map(c => c.trim().split(/\\s+/))
    .filter(c => c.length === 2 && c[1].endsWith('w'))
    .map(([url, w]) => [new URL(url, location.href).href, parseInt(w, 10)]);
  return {
    slot: slotKey(img),
    src: img.getAttribute('src'),
    slot_width: img.getBoundingClientRect().width,
    sizes: img.getAttribute('sizes'),
    lazy: img.loading === 'lazy',
    has_srcset: candidates.length > 0,
    vector: /\\.svg([?#]|$)/i.test(img.currentSrc),
    candidates,
    current_src: img.currentSrc,
    // The injector sets `width` to the source file's width.
    source_width: parseInt(img.getAttribute('width'), 10) || 0,
  };
}
"""
)


def split_sizes(sizes: str) -> list[tuple[str, str]]:
    """Split a `sizes` value into (media condition, length) pairs.

    Entries are split at top-level commas, so commas inside `min()` stay.
    The length is an entry's last token: a function such as
    `calc(50vw - 22px)`, whose spaces a whitespace split would break, or a
    plain length. What precedes it is the media condition, empty when none.
    """
    entries, depth, start = [], 0, 0
    for i, char in enumerate(sizes):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            entries.append(sizes[start:i])
            start = i + 1
    entries.append(sizes[start:])

    pairs = []
    for entry in filter(None, (e.strip() for e in entries)):
        if entry.endswith(")"):
            depth, i = 0, len(entry) - 1
            for i in range(len(entry) - 1, -1, -1):
                if entry[i] == ")":
                    depth += 1
                elif entry[i] == "(":
                    depth -= 1
                    if depth == 0:
                        break
            start = len(re.search(r"^.*?(?=[a-z-]*$)", entry[:i], re.IGNORECASE).group(0))
        else:
            start = len(entry) - len(entry.split()[-1])
        pairs.append((entry[:start].strip(), entry[start:]))
    return pairs


def sizes_to_resolve(sizes: str | None, lazy: bool) -> list[tuple[str, str]] | None:
    """Return the `sizes` pairs the browser would consult, or None when none apply.

    `auto` first on a lazy image means the laid-out width, so nothing is
    declared; elsewhere `auto` is ignored.
    """
    if not sizes:
        return None
    pairs = split_sizes(sizes)
    if pairs and pairs[0] == ("", "auto") and lazy:
        return None
    return [pair for pair in pairs if pair != ("", "auto")] or None


# Returns the width of the first `sizes` entry whose media condition
# matches, measured on a probe element, or null when none matches.
RESOLVE_SIZES_JS = """
pairs => {
  for (const [condition, length] of pairs) {
    if (condition && !matchMedia(condition).matches) continue;
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;visibility:hidden;width:' + length;
    document.body.appendChild(probe);
    const px = probe.getBoundingClientRect().width;
    probe.remove();
    return px;
  }
  return null;
}
"""


# Resolves to the last Largest Contentful Paint entry's element. Buffered
# entries arrive in the observer's first callback; a page whose paint the
# browser did not record resolves to null after a short wait, which fails
# the check rather than passing it.
LARGEST_PAINT_JS = (
    """
() => new Promise(resolve => {
  const slotKey = """
    + SLOT_KEY_JS
    + """;
  const describe = entry => {
    const element = entry && entry.element;
    if (!element) return null;
    if (element.tagName !== 'IMG') return {element: element.tagName.toLowerCase(), lazy: false};
    return {element: slotKey(element) + ' ' + element.getAttribute('src'), lazy: element.loading === 'lazy'};
  };
  new PerformanceObserver(list => {
    const entries = list.getEntries();
    resolve(describe(entries[entries.length - 1]));
  }).observe({type: 'largest-contentful-paint', buffered: true});
  setTimeout(() => resolve(null), 2000);
})
"""
)


# Decodes a file and returns its displayed width (EXIF orientation applied,
# as for an <img>).
FILE_WIDTH_JS = """
async url => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(url + ' returned ' + response.status);
  const bitmap = await createImageBitmap(await response.blob());
  const width = bitmap.width;
  bitmap.close();
  return width;
}
"""


async def file_width(page, url: str, cache: dict[str, int]) -> int:
    """Return the decoded width of the file at `url`, decoding each URL once."""
    if url not in cache:
        cache[url] = await page.evaluate(FILE_WIDTH_JS, url)
    return cache[url]


async def to_measurement(browser_page, data: dict, cache: dict[str, int], **where) -> Measurement:
    """Turn MEASURE_JS output into a Measurement, decoding the files it names."""
    candidates = data.pop("candidates")
    current_src = data.pop("current_src")
    source_width = data.pop("source_width")
    if data["vector"]:
        return Measurement(**where, **data, delivered=0, widest_available=0)

    widths = {url: await file_width(browser_page, url, cache) for url, _ in candidates}
    mismatches = tuple(
        f"{url} is {widths[url]}w, srcset says {declared}w"
        for url, declared in candidates
        if widths[url] != declared
    )
    return Measurement(
        **where,
        **data,
        delivered=await file_width(browser_page, current_src, cache),
        widest_available=max([source_width, *widths.values()]),
        mismatches=mismatches,
    )


async def measure_page(context, page_path: str, slots: set[str], viewport: int, dpr: int, cache):
    """Measure the first IMAGES_PER_SLOT images of each wanted slot on a page."""
    # Imported here so the browser-free functions load without Playwright.
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    page = await context.new_page()
    try:
        await page.goto(SITE_ORIGIN + page_path, wait_until="load")
        taken: dict[str, int] = defaultdict(int)
        results = []
        for handle in await page.query_selector_all("img"):
            slot = await handle.evaluate(SLOT_KEY_JS)
            if slot not in slots or taken[slot] >= IMAGES_PER_SLOT:
                continue
            if not await handle.evaluate("img => img.getBoundingClientRect().width > 0"):
                continue
            taken[slot] += 1
            await handle.scroll_into_view_if_needed()
            try:
                await page.wait_for_function(
                    "img => img.complete && img.currentSrc !== ''", arg=handle, timeout=10_000
                )
            except PlaywrightTimeout as error:
                src = await handle.get_attribute("src")
                raise RuntimeError(
                    f"{page_path} @ {viewport}px {dpr}x: `{slot}` {src} never loaded"
                ) from error
            data = await handle.evaluate(MEASURE_JS)
            pairs = sizes_to_resolve(data.pop("sizes"), data.pop("lazy"))
            data["declared"] = await page.evaluate(RESOLVE_SIZES_JS, pairs) if pairs else None
            results.append(
                await to_measurement(page, data, cache, page=page_path, viewport=viewport, dpr=dpr)
            )
        return results
    finally:
        await page.close()


def route_handler(site: Path, baseurl: str, origins: tuple[str, ...]):
    """Serve `_site/` for requests to `origins`; every other request gets 404.

    The production origin is served too, because absolute `src` values name
    it; no request leaves the machine. Paths are percent-decoded, so pages
    with non-ASCII names resolve to their files.
    """
    root = site.resolve()

    async def handle(route):
        url = route.request.url
        origin = next((o for o in origins if url.startswith(o + "/")), None)
        if origin is None:
            await route.fulfill(status=404, body="")
            return
        path = unquote(url[len(origin) :].split("?")[0].split("#")[0]).removeprefix(baseurl)
        file = (root / path.lstrip("/")).resolve()
        if file.is_dir():
            file = file / "index.html"
        if file.is_file() and file.is_relative_to(root):
            await route.fulfill(path=str(file))
        else:
            await route.fulfill(status=404, body="")

    return handle


async def largest_paint(context, page_path: str, viewport: int) -> LargestPaint:
    """Load a page and return its Largest Contentful Paint element.

    Waits for the network to go idle, not for `load`: a lazy image does not
    delay `load`, so at `load` the largest paint can still be text.
    """
    page = await context.new_page()
    try:
        await page.goto(SITE_ORIGIN + page_path, wait_until="networkidle")
        found = await page.evaluate(LARGEST_PAINT_JS) or {"element": None, "lazy": False}
        return LargestPaint(page=page_path, viewport=viewport, **found)
    finally:
        await page.close()


async def measure_site(
    site: Path, baseurl: str, site_url: str, sampled: dict[str, list[str]], paint_pages: list[str]
) -> tuple[list[Measurement], list[LargestPaint]]:
    """Measure the sampled pages at every viewport width and pixel density.

    At 1x, also read the Largest Contentful Paint element of `paint_pages`.
    """
    from playwright.async_api import async_playwright

    by_page: dict[str, set[str]] = defaultdict(set)
    for slot, paths in sampled.items():
        for path in paths:
            by_page[path].add(slot)

    handler = route_handler(site, baseurl, (SITE_ORIGIN, site_url.rstrip("/")))
    widths = viewport_widths(*(source.read_text() for source in BREAKPOINT_SOURCES))
    results: list[Measurement] = []
    paints: list[LargestPaint] = []
    file_widths: dict[str, int] = {}
    limit = asyncio.Semaphore(4)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def run(viewport: int, dpr: int) -> None:
            async with limit:
                context = await browser.new_context(
                    viewport={"width": viewport, "height": VIEWPORT_HEIGHT},
                    device_scale_factor=dpr,
                )
                await context.route("**/*", handler)
                try:
                    for path, slots in sorted(by_page.items()):
                        results.extend(
                            await measure_page(
                                context, baseurl + path, slots, viewport, dpr, file_widths
                            )
                        )
                finally:
                    await context.close()

        async def paint(viewport: int) -> None:
            async with limit:
                context = await browser.new_context(
                    viewport={"width": viewport, "height": VIEWPORT_HEIGHT}
                )
                await context.route("**/*", handler)
                try:
                    for path in paint_pages:
                        paints.append(await largest_paint(context, baseurl + path, viewport))
                finally:
                    await context.close()

        await asyncio.gather(
            *(run(w, d) for w in widths for d in DPRS), *(paint(w) for w in widths)
        )
        await browser.close()
    return results, paints


def report(
    measurements: list[Measurement],
    sampled: dict[str, list[str]],
    paints: list[LargestPaint] = (),
    max_width: int | None = None,
) -> tuple[str, list[str]]:
    """Return a per-slot summary table and the list of failures.

    Every slot in `sampled` must have been measured at least once, and no
    Largest Contentful Paint element in `paints` may be a lazy image.
    """
    by_slot: dict[str, list[Measurement]] = defaultdict(list)
    for m in measurements:
        by_slot[m.slot].append(m)

    lines = [
        "| Slot | srcset | Slot width (CSS px) | 1x / 2x need | Delivered widths |",
        "|---|---|---|---|---|",
    ]
    for slot, ms in sorted(by_slot.items()):
        widths = [m.slot_width for m in ms]
        widest = max(widths)
        if any(m.vector for m in ms):
            need = "vector"
        else:
            need = f"{math.ceil(widest)} / {math.ceil(widest * MAX_USEFUL_DPR)}"
        delivered = sorted({m.delivered for m in ms if not m.vector})
        shown = ", ".join(map(str, delivered[:6])) + (" ..." if len(delivered) > 6 else "")
        lines.append(
            f"| `{slot}` | {'yes' if any(m.has_srcset for m in ms) else 'no'} "
            f"| {min(widths):.0f}-{widest:.0f} | {need} | {shown or '-'} |"
        )

    failures = [
        f"`{slot}` on {', '.join(pages)} was never visible, so it was not measured"
        for slot, pages in sampled.items()
        if slot not in by_slot
    ]
    for m in measurements:
        for problem in problems(m, max_width):
            failures.append(f"{m.page} @ {m.viewport}px {m.dpr}x `{m.slot}` {m.src}: {problem}")
    for paint in paints:
        if paint.element is None:
            failures.append(
                f"{paint.page} @ {paint.viewport}px: no Largest Contentful Paint reading, "
                "so the lazy-image check could not run"
            )
        elif paint.lazy:
            failures.append(
                f"{paint.page} @ {paint.viewport}px: the Largest Contentful Paint element, "
                f'`{paint.element}`, has loading="lazy"'
            )
    return "\n".join(lines), sorted(set(failures))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("site", type=Path, help="the built site directory (_site)")
    parser.add_argument("--baseurl", default="", help="the site's baseurl, if any")
    parser.add_argument(
        "--site-url",
        default="https://hfgude.com",
        help="the production URL that absolute src values use",
    )
    args = parser.parse_args(argv)

    if not (args.site / "index.html").is_file():
        print(f"error: {args.site} is not a built site (no index.html)", file=sys.stderr)
        return EXIT_UNUSABLE

    paint_pages = chosen_pages(args.site)
    sampled = sample_pages(args.site, paint_pages)
    measurements, paints = asyncio.run(
        measure_site(args.site, args.baseurl.rstrip("/"), args.site_url, sampled, paint_pages)
    )
    if not measurements:
        print("error: measured no images", file=sys.stderr)
        return EXIT_UNUSABLE

    table, failures = report(measurements, sampled, paints, max_copy_width(CONFIG.read_text()))
    print(table)
    print(
        f"\n{len(measurements)} measurements, {len(paints)} paints on "
        f"{len(paint_pages)} pages, {len(failures)} failures"
    )
    for failure in failures:
        print(f"FAIL {failure}")
    return EXIT_FAILED if failures else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
