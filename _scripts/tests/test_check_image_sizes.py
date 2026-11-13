"""Tests for the browser-free parts of ci/check_image_sizes.py.

The browser measurement itself runs in `make check-images`; these tests
cover the checks applied to its measurements, the viewport widths derived
from the stylesheet and layouts, how pages are sampled, and the lazy
Largest Contentful Paint failure.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from check_image_sizes import (
    BREAKPOINT_SOURCES,
    CONFIG,
    EXIT_UNUSABLE,
    SAMPLE_PAGES,
    SITE_ORIGIN,
    LargestPaint,
    Measurement,
    artwork_pages,
    chosen_pages,
    main,
    max_copy_width,
    missing_sample_pages,
    problems,
    report,
    route_handler,
    sample_pages,
    sizes_to_resolve,
    slot_key,
    split_sizes,
    viewport_widths,
)


def measure(**overrides) -> Measurement:
    """A passing srcset measurement: a 300px slot at 1x given a 300w file."""
    values = {
        "page": "/human-figure/paintings/",
        "viewport": 1280,
        "dpr": 1,
        "slot": ".photo-grid img",
        "src": "/assets/images/galleries/a.jpg",
        "slot_width": 300.0,
        "declared": 300.0,
        "has_srcset": True,
        "vector": False,
        "delivered": 300,
        "widest_available": 1000,
    }
    values.update(overrides)
    return Measurement(**values)


# --- problems ---


def test_matching_measurement_passes():
    assert problems(measure()) == []


@pytest.mark.parametrize("declared", [250.0, 340.0])
def test_sizes_outside_tolerance_fails(declared):
    [problem] = problems(measure(declared=declared, delivered=600))
    assert "sizes declares" in problem


def test_auto_sizes_is_not_compared():
    assert problems(measure(declared=None)) == []


def test_too_narrow_file_fails_when_source_is_wider():
    [problem] = problems(measure(dpr=2, delivered=300))
    assert "for a 600px need" in problem


def test_too_narrow_file_passes_when_source_is_the_limit():
    assert problems(measure(dpr=2, delivered=300, widest_available=300)) == []


def test_need_above_the_widest_copy_passes_at_that_copy():
    wide = measure(slot_width=1600.0, declared=1600.0, dpr=2, delivered=2400, widest_available=4000)
    assert problems(wide, max_width=2400) == []
    [problem] = problems(wide)
    assert "for a 3200px need" in problem


def test_three_x_needs_only_two_x():
    assert problems(measure(dpr=3, delivered=600)) == []


def test_oversized_file_fails():
    [problem] = problems(measure(slot_width=140.0, declared=None, delivered=300))
    assert "over 2x" in problem


@pytest.mark.parametrize(
    "overrides",
    [{"has_srcset": False}, {"vector": True}, {"slot_width": 0.0}],
)
def test_unchecked_images_pass(overrides):
    assert problems(measure(delivered=4000, declared=10.0, **overrides)) == []


def test_wrong_descriptor_fails():
    mismatch = "/d/one.webp is 1w, srcset says 600w"
    [problem] = problems(measure(mismatches=(mismatch,)))
    assert mismatch in problem


# --- report ---


def test_report_fails_slot_never_measured():
    table, failures = report([measure()], {".photo-grid img": ["/a/"], ".hidden img": ["/b/"]})
    assert "`.photo-grid img`" in table
    assert failures == ["`.hidden img` on /b/ was never visible, so it was not measured"]


def test_report_fails_lazy_largest_paint():
    paints = [
        LargestPaint("/", 390, ".gallery-grid img /c.jpg", True),
        LargestPaint("/artwork/a/", 390, ".artwork-full-size img /d.jpg", False),
        LargestPaint("/by-medium/", 390, "h1", False),
    ]
    _, failures = report([measure()], {".photo-grid img": ["/a/"]}, paints)
    assert failures == [
        "/ @ 390px: the Largest Contentful Paint element, "
        '`.gallery-grid img /c.jpg`, has loading="lazy"'
    ]


def test_report_fails_missing_paint_reading():
    _, failures = report(
        [measure()], {".photo-grid img": ["/a/"]}, [LargestPaint("/x/", 390, None, False)]
    )
    assert failures == [
        "/x/ @ 390px: no Largest Contentful Paint reading, so the lazy-image check could not run"
    ]


# --- split_sizes and sizes_to_resolve ---


def test_split_sizes_keeps_function_lengths_whole():
    sizes = (
        "(min-width: 64.375em) 311px, (min-width: 60.125em) calc((100vw - 98px) / 3), "
        "min(100vw - 50px, 1600px, 85vh * 745 / 982, 745px)"
    )
    assert split_sizes(sizes) == [
        ("(min-width: 64.375em)", "311px"),
        ("(min-width: 60.125em)", "calc((100vw - 98px) / 3)"),
        ("", "min(100vw - 50px, 1600px, 85vh * 745 / 982, 745px)"),
    ]


def test_split_sizes_plain_and_compound_conditions():
    assert split_sizes("auto, (min-width: 38em) and (max-width: 60em) 300px, 240px") == [
        ("", "auto"),
        ("(min-width: 38em) and (max-width: 60em)", "300px"),
        ("", "240px"),
    ]


def test_auto_on_lazy_image_declares_nothing():
    assert sizes_to_resolve("auto, 300px", lazy=True) is None
    assert sizes_to_resolve("auto, 300px", lazy=False) == [("", "300px")]
    assert sizes_to_resolve(None, lazy=False) is None


# --- viewport_widths and max_copy_width ---


def test_widths_bracket_each_breakpoint():
    widths = viewport_widths("@media (max-width: 37.4375em) {", 'sizes="(min-width: 64em) 1px"')
    assert {598, 599, 600, 1023, 1024, 1025} <= set(widths)
    assert widths == sorted(widths)


def test_real_sources_have_breakpoints():
    widths = viewport_widths(*(source.read_text() for source in BREAKPOINT_SOURCES))
    assert {598, 599, 600, 1029, 1030, 1031} <= set(widths)


def test_max_copy_width_reads_every_entry():
    config = "a:\n  - widths: [300, 600]\n  - widths: [300, 2400, 900]\n"
    assert max_copy_width(config) == 2400
    assert max_copy_width("title: x\n") is None


def test_real_config_has_widths():
    assert max_copy_width(CONFIG.read_text()) is not None


# --- slot_key and page sampling ---


def test_slot_key_prefers_id_then_class_then_ancestor():
    assert slot_key("lead", ["x"], [["post"]]) == "#lead"
    assert slot_key(None, ["thumb"], [["post"]]) == "img.thumb"
    assert slot_key(None, [], [[], [], [], ["photo-grid"]]) == ".photo-grid img"
    assert slot_key(None, [], [[]] * 4 + [["far"]]) == "img"


def write_page(site: Path, path: str, body: str) -> None:
    page = site / path / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"<!doctype html><html><body>{body}</body></html>")


def artwork(width: int, height: int) -> str:
    return f'<a class="artwork-full-size" href="/a.jpg"><img src="/a.jpg" width="{width}" height="{height}"></a>'


def test_artwork_pages_take_each_shape(tmp_path):
    for name, size in {
        "tall": (500, 1000),
        "taller": (400, 1000),
        "square": (800, 790),
        "wide": (1000, 500),
        "mid": (900, 700),
    }.items():
        write_page(tmp_path, f"artwork/{name}", artwork(*size))

    assert artwork_pages(tmp_path, per_shape=1) == [
        "/artwork/square/",
        "/artwork/taller/",
        "/artwork/wide/",
    ]


def test_chosen_pages_lists_sample_pages_then_artworks(tmp_path):
    write_page(tmp_path, "artwork/x", artwork(10, 10))
    assert chosen_pages(tmp_path) == [*SAMPLE_PAGES, "/artwork/x/"]


def test_missing_sample_pages_names_each_absent_page(tmp_path):
    for path in SAMPLE_PAGES[1:]:
        write_page(tmp_path, path.strip("/"), "<p></p>")
    assert missing_sample_pages(tmp_path) == ["/"]


def test_main_stops_when_a_sample_page_is_missing(tmp_path, capsys):
    write_page(tmp_path, ".", "<p></p>")
    assert main([str(tmp_path)]) == EXIT_UNUSABLE
    assert "sample pages missing" in capsys.readouterr().err


def test_sample_pages_maps_slots_to_pages(tmp_path):
    write_page(tmp_path, ".", '<ul class="gallery-grid"><li><a><img src="/a.jpg"></a></li></ul>')
    write_page(tmp_path, "about", '<figure class="bio-figure"><img src="/b.jpg"></figure>')
    write_page(tmp_path, "other", '<figure class="bio-figure"><img src="/b.jpg"></figure>')

    assert sample_pages(tmp_path, ["/", "/about/"]) == {
        ".gallery-grid img": ["/"],
        ".bio-figure img": ["/about/"],
    }


def test_route_handler_serves_percent_encoded_paths(tmp_path):
    page = tmp_path / "artwork" / "café" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text("<p>Café</p>", encoding="utf-8")
    served = {}

    async def fulfill(**kwargs):
        served.update(kwargs)

    route = SimpleNamespace(
        request=SimpleNamespace(url=f"{SITE_ORIGIN}/artwork/caf%C3%A9/"), fulfill=fulfill
    )
    asyncio.run(route_handler(tmp_path, "", (SITE_ORIGIN,))(route))

    assert served == {"path": str(page.resolve())}
