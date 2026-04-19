"""Tests for render_adapter: per-layout content emission + workspace fanout."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from presentation_forge.layouts import Layout
from presentation_forge.render_adapter import (
    DEFAULT_AZURE_LAYOUTS,
    DEFAULT_PLACEHOLDER_ROLES,
    materialize_workspace,
    slide_to_content,
)
from presentation_forge.slides_parser import Slide
from presentation_forge.spec import Selection, load_presentation


# ---------------------------------------------------------------------------
# slide_to_content — per-layout shape verification
# ---------------------------------------------------------------------------


def _slide(**overrides) -> Slide:
    base = {"slide-id": "s", "layout": "title", "title": "T"}
    base.update(overrides)
    return Slide.from_block(base)


def test_title_layout_fills_title_and_subtitle_placeholders():
    s = _slide(title="Hello", subtitle="Sub")
    c = slide_to_content(s)
    assert c["layout"] == "title"
    assert c["title"] == "Hello"
    roles = DEFAULT_PLACEHOLDER_ROLES["title"]
    assert c["placeholders"][roles.title] == "Hello"
    assert c["placeholders"][roles.body] == "Sub"
    assert "elements" not in c


def test_section_divider_emits_subtitle_as_textbox():
    s = _slide(layout="section-divider", title="Part 1", subtitle="next up")
    c = slide_to_content(s)
    assert c["title"] == "Part 1"
    assert c["placeholders"][0] == "Part 1"
    # subtitle is a textbox element
    elems = c.get("elements", [])
    assert len(elems) == 1 and elems[0]["type"] == "textbox"
    assert elems[0]["text"] == "next up"


def test_bullets_layout_writes_list_to_body_placeholder():
    s = _slide(
        layout="bullets",
        title="three",
        bullets=["one", "two", "three"],
    )
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["bullets"]
    assert c["placeholders"][roles.body] == ["one", "two", "three"]


def test_bullets_with_image_right_position():
    s = _slide(
        layout="bullets-with-image",
        title="t",
        bullets=["a", "b"],
        image_ref="hero",
        image_position="right",
    )
    c = slide_to_content(
        s,
        image_paths=[Path("/tmp/hero_v01_i01.png")],
    )
    elems = c["elements"]
    assert len(elems) == 1 and elems[0]["type"] == "image"
    assert elems[0]["path"].endswith("hero_v01_i01.png")
    # right-positioned: left coord is past mid-line
    assert elems[0]["left"] > 6.0


def test_bullets_with_image_left_position():
    s = _slide(
        layout="bullets-with-image",
        title="t",
        bullets=["a"],
        image_ref="hero",
        image_position="left",
    )
    c = slide_to_content(s, image_paths=[Path("/tmp/x.png")])
    assert c["elements"][0]["left"] < 1.0


def test_bullets_with_image_no_image_yet():
    s = _slide(
        layout="bullets-with-image",
        title="t",
        bullets=["a"],
        image_ref="hero",
    )
    c = slide_to_content(s, image_paths=[])
    assert "elements" not in c
    # body placeholder still filled
    roles = DEFAULT_PLACEHOLDER_ROLES["bullets-with-image"]
    assert c["placeholders"][roles.body] == ["a"]


def test_full_bleed_image_with_image_uses_fallback_dims():
    s = _slide(layout="full-bleed-image", title="hero", image_ref="x")
    c = slide_to_content(s, image_paths=[Path("/tmp/x.png")])
    elems = c["elements"]
    assert len(elems) == 1 and elems[0]["type"] == "image"
    # Falls back to full canvas when no template provided.
    assert elems[0]["left"] == 0.0
    assert elems[0]["top"] == 0.0


def test_full_bleed_image_without_image_emits_nothing():
    s = _slide(layout="full-bleed-image", title="hero", image_ref="x")
    c = slide_to_content(s, image_paths=[])
    assert "elements" not in c


def test_two_column_partitions_bullets_even_odd():
    s = _slide(
        layout="two-column",
        title="t",
        bullets=["L1", "R1", "L2", "R2", "L3"],
    )
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["two-column"]
    assert c["placeholders"][roles.body] == ["L1", "L2", "L3"]
    assert c["placeholders"][roles.secondary] == ["R1", "R2"]


def test_comparison_layout_uses_same_partitioning():
    s = _slide(
        layout="comparison",
        title="vs",
        bullets=["a1", "b1", "a2", "b2"],
    )
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["comparison"]
    assert c["placeholders"][roles.body] == ["a1", "a2"]
    assert c["placeholders"][roles.secondary] == ["b1", "b2"]


def test_quote_wraps_body_in_smart_quotes_and_em_dash_attribution():
    s = _slide(
        layout="quote",
        body="Be the change.",
        subtitle="Gandhi",
    )
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["quote"]
    assert c["placeholders"][roles.body] == "\u201cBe the change.\u201d"
    assert c["placeholders"][roles.secondary] == "\u2014 Gandhi"


def test_quote_without_attribution_omits_secondary():
    s = _slide(layout="quote", body="Just a thought.")
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["quote"]
    assert roles.secondary not in c.get("placeholders", {})


def test_image_grid_lays_out_three_tiles():
    s = _slide(layout="image-grid", title="Grid")
    paths = [Path(f"/tmp/g{i}.png") for i in range(3)]
    c = slide_to_content(s, image_paths=paths)
    elems = c["elements"]
    assert len(elems) == 3
    # Tiles march left-to-right with growing 'left'
    lefts = [e["left"] for e in elems]
    assert lefts == sorted(lefts)
    # All same width and height
    widths = {e["width"] for e in elems}
    heights = {e["height"] for e in elems}
    assert len(widths) == 1 and len(heights) == 1


def test_image_grid_caps_at_three_images():
    s = _slide(layout="image-grid", title="Grid")
    paths = [Path(f"/tmp/g{i}.png") for i in range(5)]
    c = slide_to_content(s, image_paths=paths)
    assert len(c["elements"]) == 3


def test_appendix_references_falls_back_to_body_when_no_bullets():
    s = Slide.from_block(
        {
            "slide-id": "ref",
            "layout": "appendix-references",
            "title": "Refs",
            "body": "Just a paragraph.",
        }
    )
    c = slide_to_content(s)
    roles = DEFAULT_PLACEHOLDER_ROLES["appendix-references"]
    assert c["placeholders"][roles.body] == ["Just a paragraph."]


def test_label_suffix_appends_to_title():
    s = _slide(title="Original")
    c = slide_to_content(s, label_suffix="(draft)")
    assert c["title"] == "Original (draft)"
    assert c["placeholders"][0] == "Original (draft)"


def test_label_suffix_alone_becomes_title_when_slide_has_no_title():
    s = Slide.from_block(
        {"slide-id": "h", "layout": "full-bleed-image", "image_ref": "x"}
    )
    c = slide_to_content(s, label_suffix="(no images yet)")
    assert c["title"] == "(no images yet)"


def test_extra_elements_passthrough_appended_after_adapter_elements():
    s = Slide.from_block(
        {
            "slide-id": "g",
            "layout": "image-grid",
            "title": "Grid",
            "extra_elements": [
                {"type": "textbox", "left": 0, "top": 7, "width": 13, "height": 0.4,
                 "text": "footer", "font_size": 10},
            ],
        }
    )
    c = slide_to_content(s, image_paths=[Path(f"/tmp/g{i}.png") for i in range(2)])
    elems = c["elements"]
    assert len(elems) == 3  # 2 images + 1 textbox
    assert elems[-1]["type"] == "textbox"
    assert elems[-1]["text"] == "footer"


def test_extra_elements_passthrough_on_layout_with_no_other_elements():
    s = Slide.from_block(
        {
            "slide-id": "t",
            "layout": "title",
            "title": "Hi",
            "extra_elements": [
                {"type": "shape", "shape_type": "rectangle", "left": 0, "top": 0,
                 "width": 1, "height": 1, "fill": "#000"},
            ],
        }
    )
    c = slide_to_content(s)
    assert c["elements"] == [
        {"type": "shape", "shape_type": "rectangle", "left": 0, "top": 0,
         "width": 1, "height": 1, "fill": "#000"},
    ]


def test_notes_are_passed_through_stripped():
    s = Slide.from_block(
        {"slide-id": "x", "layout": "title", "title": "T", "notes": "  hello  \n"}
    )
    c = slide_to_content(s)
    assert c["notes"] == "hello"


def test_empty_bullets_emit_no_body_placeholder():
    s = Slide.from_block(
        {"slide-id": "x", "layout": "bullets", "title": "t", "bullets": ["", "  "]}
    )
    c = slide_to_content(s)
    # all bullets were blank; expect no body key
    roles = DEFAULT_PLACEHOLDER_ROLES["bullets"]
    assert roles.body not in c.get("placeholders", {})


def test_default_layout_mapping_covers_every_layout():
    for layout in Layout:
        assert layout.value in DEFAULT_AZURE_LAYOUTS
        assert layout.value in DEFAULT_PLACEHOLDER_ROLES


# ---------------------------------------------------------------------------
# materialize_workspace — draft & final modes
# ---------------------------------------------------------------------------


def test_materialize_workspace_draft_fans_out_image_variants(
    make_presentation_dir, populate_image_variants, tmp_path
):
    folder = make_presentation_dir("deck")
    populate_image_variants(folder, "hero-img", variations=3)
    populate_image_variants(folder, "side-img", variations=2)
    pres = load_presentation(folder)

    workdir = tmp_path / "ws"
    paths = materialize_workspace(pres, workdir=workdir, mode="draft")

    # 6 logical slides; hero (3 variants) + side (2 variants) + 4 plain = 9 emitted
    assert len(paths.slide_dirs) == 1 + 3 + 1 + 2 + 1 + 1
    style = yaml.safe_load(paths.style_path.read_text(encoding="utf-8"))
    assert "layouts" in style
    # No template configured -> no template entry
    assert "template" not in style

    # Each draft slide for an image-bearing layout copied its variant PNG.
    hero_drafts = [d for d in paths.slide_dirs if (d / "images").exists()]
    assert len(hero_drafts) >= 5  # 3 hero + 2 side


def test_materialize_workspace_draft_emits_no_image_label_when_variants_missing(
    make_presentation_dir, tmp_path
):
    folder = make_presentation_dir("deck")
    pres = load_presentation(folder)
    workdir = tmp_path / "ws"

    paths = materialize_workspace(pres, workdir=workdir, mode="draft")
    # Find the hero slide content; title should include "(no images yet)"
    contents = [
        yaml.safe_load((d / "content.yaml").read_text(encoding="utf-8"))
        for d in paths.slide_dirs
    ]
    titles = [c.get("title", "") for c in contents]
    assert any("no images yet" in t for t in titles)


def test_materialize_workspace_final_uses_selection(
    make_presentation_dir, populate_image_variants, tmp_path
):
    folder = make_presentation_dir("deck")
    populate_image_variants(folder, "hero-img", variations=3)
    populate_image_variants(folder, "side-img", variations=2)
    # Select v02 of hero for slide "hero"
    import json

    sel = {
        "hero": {"model": "gpt-image-1", "variation": 2, "instance": 1},
        "side": None,
    }
    (folder / "selections.json").write_text(json.dumps(sel), encoding="utf-8")
    pres = load_presentation(folder)

    paths = materialize_workspace(pres, workdir=tmp_path / "ws", mode="final")
    assert len(paths.slide_dirs) == 6  # one per slide

    # Slide 2 is the hero. Its images dir should contain the selected variant.
    hero_dir = paths.slide_dirs[1]
    files = list((hero_dir / "images").iterdir())
    assert any("v02_i01" in f.name for f in files)

    # Slide 4 is the side-by-side; no selection -> no image included.
    side_dir = paths.slide_dirs[3]
    assert not (side_dir / "images").exists() or not list(
        (side_dir / "images").iterdir()
    )


def test_materialize_workspace_rejects_unknown_mode(make_presentation_dir, tmp_path):
    pres = load_presentation(make_presentation_dir("deck"))
    with pytest.raises(ValueError, match="mode must be"):
        materialize_workspace(pres, workdir=tmp_path / "ws", mode="bogus")


def test_materialize_workspace_overwrites_existing_dir(
    make_presentation_dir, tmp_path
):
    pres = load_presentation(make_presentation_dir("deck"))
    workdir = tmp_path / "ws"
    workdir.mkdir()
    (workdir / "stale.txt").write_text("delete me")

    materialize_workspace(pres, workdir=workdir, mode="final")
    assert not (workdir / "stale.txt").exists()


def test_materialize_workspace_emits_template_block_when_set(
    make_presentation_dir, microsoft_template_path, tmp_path
):
    folder = make_presentation_dir("deck", with_template=True)
    pres = load_presentation(folder)
    paths = materialize_workspace(pres, workdir=tmp_path / "ws", mode="final")

    assert paths.template_path is not None
    assert paths.template_path.exists()
    style = yaml.safe_load(paths.style_path.read_text(encoding="utf-8"))
    assert style["template"]["path"] == str(paths.template_path)
    # All adapter-default layouts plus theme overrides present.
    assert style["layouts"]["title"] == "Title Slide 1"


def test_materialize_workspace_full_bleed_uses_template_picture_dims(
    make_presentation_dir, populate_image_variants, microsoft_template_path, tmp_path
):
    folder = make_presentation_dir("deck", with_template=True)
    populate_image_variants(folder, "hero-img", variations=1)
    import json

    (folder / "selections.json").write_text(
        json.dumps(
            {"hero": {"model": "gpt-image-1", "variation": 1, "instance": 1}}
        ),
        encoding="utf-8",
    )
    pres = load_presentation(folder)
    paths = materialize_workspace(pres, workdir=tmp_path / "ws", mode="final")
    hero_content = yaml.safe_load(
        (paths.slide_dirs[1] / "content.yaml").read_text(encoding="utf-8")
    )
    elems = hero_content["elements"]
    assert len(elems) == 1 and elems[0]["type"] == "image"
    # When the template is present, the picture-placeholder dims kick in,
    # and they are NOT the full-canvas fallback (which would be 0/0/13.333/7.5).
    assert (elems[0]["left"], elems[0]["top"]) != (0.0, 0.0) or (
        elems[0]["width"],
        elems[0]["height"],
    ) != (13.333, 7.5)
