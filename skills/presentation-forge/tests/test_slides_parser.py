"""Tests for slides_parser, focusing on extra_elements and validation."""
from __future__ import annotations

from textwrap import dedent

import pytest

from presentation_forge.layouts import Layout
from presentation_forge.slides_parser import Slide, parse_slides_md


def _write(tmp_path, body: str):
    p = tmp_path / "slides.md"
    p.write_text(dedent(body), encoding="utf-8")
    return p


def test_basic_parse(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: title
        layout: title
        title: Hello
        ---
        """,
    )
    slides = parse_slides_md(p)
    assert len(slides) == 1
    s = slides[0]
    assert s.slide_id == "title"
    assert s.layout is Layout.TITLE
    assert s.title == "Hello"
    assert s.extra_elements == []


def test_extra_elements_passthrough(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: fancy
        layout: title
        title: Hello
        extra_elements:
          - type: textbox
            left: 1.0
            top: 2.0
            width: 4.0
            height: 0.5
            text: "Watermark"
            font_size: 10
          - type: shape
            shape_type: rectangle
            left: 0
            top: 0
            width: 13.333
            height: 0.5
            fill: "#0078D4"
        ---
        """,
    )
    s = parse_slides_md(p)[0]
    assert len(s.extra_elements) == 2
    assert s.extra_elements[0]["type"] == "textbox"
    assert s.extra_elements[1]["fill"] == "#0078D4"


def test_extra_elements_must_be_list_of_dicts(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: bad
        layout: title
        title: hi
        extra_elements:
          - "not a dict"
        ---
        """,
    )
    with pytest.raises(ValueError, match="extra_elements"):
        parse_slides_md(p)


def test_extra_elements_not_a_list(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: bad
        layout: title
        title: hi
        extra_elements:
          foo: bar
        ---
        """,
    )
    with pytest.raises(ValueError, match="extra_elements"):
        parse_slides_md(p)


def test_extra_elements_omitted_yields_empty_list(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: ok
        layout: title
        title: hi
        ---
        """,
    )
    s = parse_slides_md(p)[0]
    assert s.extra_elements == []


def test_invalid_slide_id_rejected(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: "Bad ID"
        layout: title
        title: x
        ---
        """,
    )
    with pytest.raises(ValueError, match="slide-id must be kebab-case"):
        parse_slides_md(p)


def test_unknown_layout_rejected(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: foo
        layout: nonsense
        title: x
        ---
        """,
    )
    with pytest.raises(ValueError, match="unknown layout"):
        parse_slides_md(p)


def test_missing_required_fields_rejected(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: foo
        layout: bullets
        title: x
        ---
        """,
    )
    with pytest.raises(ValueError, match="missing required fields"):
        parse_slides_md(p)


def test_duplicate_slide_id_rejected(tmp_path):
    p = _write(
        tmp_path,
        """\
        ---
        slide-id: foo
        layout: title
        title: x
        ---

        ---
        slide-id: foo
        layout: title
        title: y
        ---
        """,
    )
    with pytest.raises(ValueError, match="duplicate slide-id"):
        parse_slides_md(p)


def test_empty_file_rejected(tmp_path):
    p = _write(tmp_path, "")
    with pytest.raises(ValueError, match="no slides found"):
        parse_slides_md(p)


def test_from_block_round_trip():
    s = Slide.from_block({"slide-id": "x", "layout": "title", "title": "T"})
    assert s.title == "T"
    assert s.raw["slide-id"] == "x"
