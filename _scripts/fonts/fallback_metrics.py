#!/usr/bin/env python3
"""Compute @font-face overrides that make a local fallback match a web font.

For each pair of web font and fallback font, prints the `size-adjust`,
`ascent-override`, `descent-override`, and `line-gap-override` values for
an @font-face rule whose `src` is the fallback. With them, text set in
the fallback takes the same width and line height as the web font, so
the page does not shift when the web font arrives.

- size-adjust scales the fallback so its average character width, with
  letters weighted by English frequency, equals the web font's.
- The overrides are the web font's vertical metrics (hhea, or OS/2 typo
  metrics when USE_TYPO_METRICS is set) divided by size-adjust, since the
  browser applies size-adjust to them too.

Usage:
    uv run --group dev python fonts/fallback_metrics.py WEB_FONT FALLBACK [WEB_FONT FALLBACK ...]
Example:
    uv run --group dev python fonts/fallback_metrics.py \\
        ../assets/fonts/libre-baskerville-400.woff2 /usr/share/fonts/truetype/msttcorefonts/Georgia.ttf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

# English letter frequencies (percent), plus the space, which is about one
# character in six in running text.
FREQUENCIES = {
    " ": 18.0,
    "e": 12.7, "t": 9.1, "a": 8.2, "o": 7.5, "i": 7.0, "n": 6.7, "s": 6.3,
    "h": 6.1, "r": 6.0, "d": 4.3, "l": 4.0, "c": 2.8, "u": 2.8, "m": 2.4,
    "w": 2.4, "f": 2.2, "g": 2.0, "y": 2.0, "p": 1.9, "b": 1.5, "v": 1.0,
    "k": 0.8, "j": 0.15, "x": 0.15, "q": 0.1, "z": 0.07,
}  # fmt: skip
USE_TYPO_METRICS = 1 << 7


def average_width(font: TTFont) -> float:
    """Return the frequency-weighted average advance width, in em."""
    cmap = font.getBestCmap()
    advances = font["hmtx"].metrics
    total = sum(FREQUENCIES.values())
    width = sum(advances[cmap[ord(char)]][0] * weight for char, weight in FREQUENCIES.items())
    return width / total / font["head"].unitsPerEm


def vertical_metrics(font: TTFont) -> tuple[float, float, float]:
    """Return ascent, descent (positive), and line gap, in em, as browsers read them."""
    em = font["head"].unitsPerEm
    os2 = font["OS/2"]
    if os2.fsSelection & USE_TYPO_METRICS:
        return os2.sTypoAscender / em, -os2.sTypoDescender / em, os2.sTypoLineGap / em
    hhea = font["hhea"]
    return hhea.ascent / em, -hhea.descent / em, hhea.lineGap / em


def overrides(web: TTFont, fallback: TTFont) -> dict[str, str]:
    """Return the @font-face descriptors for the fallback, as CSS percentages."""
    size_adjust = average_width(web) / average_width(fallback)
    ascent, descent, line_gap = vertical_metrics(web)
    return {
        "size-adjust": f"{size_adjust * 100:.2f}%",
        "ascent-override": f"{ascent / size_adjust * 100:.2f}%",
        "descent-override": f"{descent / size_adjust * 100:.2f}%",
        "line-gap-override": f"{line_gap / size_adjust * 100:.2f}%",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("fonts", nargs="+", type=Path, help="web font and fallback pairs")
    args = parser.parse_args(argv)
    if len(args.fonts) % 2:
        parser.error("give fonts in pairs: WEB_FONT FALLBACK")

    for web_path, fallback_path in zip(args.fonts[::2], args.fonts[1::2], strict=True):
        print(f"/* {web_path.name} on {fallback_path.name} */")
        for name, value in overrides(TTFont(web_path), TTFont(fallback_path)).items():
            print(f"{name}: {value};")
    return 0


if __name__ == "__main__":
    sys.exit(main())
