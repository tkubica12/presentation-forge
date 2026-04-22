"""Tests for the Theme dataclass extensions (template/layouts/metadata/defaults)."""
from __future__ import annotations

import pytest

from presentation_forge.spec import Theme


def test_minimal_theme(tmp_path):
    t = Theme.from_dict({}, tmp_path)
    assert t.template is None
    assert t.fonts == {}
    assert t.layouts == {}
    assert t.metadata == {}
    assert t.defaults == {}


def test_full_theme(tmp_path):
    (tmp_path / "tpl.pptx").write_text("x")
    t = Theme.from_dict(
        {
            "template": "tpl.pptx",
            "fonts": {"body": "Arial"},
            "colors": {"accent": "#FF0000"},
            "logo": "logo.png",
            "layouts": {
                "title": "Title Slide 1",
                "bullets": 7,
            },
            "metadata": {"author": "me", "subject": "test"},
            "defaults": {"font_size": 18, "alignment": "left"},
        },
        tmp_path,
    )
    assert t.template == (tmp_path / "tpl.pptx").resolve()
    assert t.logo == (tmp_path / "logo.png").resolve()
    assert t.layouts == {"title": "Title Slide 1", "bullets": 7}
    assert t.metadata == {"author": "me", "subject": "test"}
    assert t.defaults == {"font_size": 18, "alignment": "left"}


def test_layouts_must_be_mapping(tmp_path):
    with pytest.raises(ValueError, match="layouts"):
        Theme.from_dict({"layouts": ["a", "b"]}, tmp_path)


def test_layouts_value_must_be_str_or_int(tmp_path):
    with pytest.raises(ValueError, match="must be string or int"):
        Theme.from_dict({"layouts": {"title": 1.5}}, tmp_path)


def test_layouts_key_must_be_string(tmp_path):
    with pytest.raises(ValueError, match="non-string key"):
        Theme.from_dict({"layouts": {1: "Title Slide 1"}}, tmp_path)


def test_metadata_must_be_mapping(tmp_path):
    with pytest.raises(ValueError, match="metadata"):
        Theme.from_dict({"metadata": "not a dict"}, tmp_path)


def test_defaults_must_be_mapping(tmp_path):
    with pytest.raises(ValueError, match="defaults"):
        Theme.from_dict({"defaults": ["nope"]}, tmp_path)


def test_metadata_values_coerced_to_string(tmp_path):
    t = Theme.from_dict({"metadata": {"foo": 42, "bar": True}}, tmp_path)
    assert t.metadata == {"foo": "42", "bar": "True"}


def test_theme_paths_accept_windows_style_backslashes(tmp_path):
    (tmp_path / "pptx-assets" / "design-templates").mkdir(parents=True)
    (tmp_path / "pptx-assets" / "design-templates" / "brand.potx").write_text("x")
    (tmp_path / "pptx-assets" / "brand-assets").mkdir(parents=True)
    (tmp_path / "pptx-assets" / "brand-assets" / "logo.png").write_text("x")

    deck = tmp_path / "talks" / "demo"
    deck.mkdir(parents=True)

    t = Theme.from_dict(
        {
            "template": r"..\..\pptx-assets\design-templates\brand.potx",
            "logo": r"..\..\pptx-assets\brand-assets\logo.png",
        },
        deck,
    )

    assert t.template == (tmp_path / "pptx-assets" / "design-templates" / "brand.potx").resolve()
    assert t.logo == (tmp_path / "pptx-assets" / "brand-assets" / "logo.png").resolve()
