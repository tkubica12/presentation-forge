"""Tests for the new slides.yaml / selections.yaml loaders and migrate."""
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from presentation_forge.cli import main as cli_main
from presentation_forge.slides_parser import parse_slides_yaml, slides_to_yaml_text
from presentation_forge.spec import (
    Selection,
    load_presentation,
    save_selections,
)


def _write_min_yaml_project(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.md").write_text("# story\n", encoding="utf-8")
    (folder / "slides.yaml").write_text(
        dedent(
            """\
            - slide-id: title
              layout: title
              title: "Hello YAML"
              subtitle: "World"
              notes: |
                Welcome.

            - slide-id: thanks
              layout: section-divider
              title: "Thanks"
              subtitle: "Q&A"
            """
        ),
        encoding="utf-8",
    )
    (folder / "images.yaml").write_text("images: []\n", encoding="utf-8")
    (folder / "theme.yaml").write_text("template: null\nlayouts: {}\n", encoding="utf-8")


def test_parse_slides_yaml_top_level_list(tmp_path: Path):
    _write_min_yaml_project(tmp_path)
    slides = parse_slides_yaml(tmp_path / "slides.yaml")
    assert [s.slide_id for s in slides] == ["title", "thanks"]
    assert slides[0].notes.strip() == "Welcome."


def test_parse_slides_yaml_dict_with_slides_key(tmp_path: Path):
    p = tmp_path / "slides.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "slides": [
                    {"slide-id": "a", "layout": "title", "title": "A"},
                    {"slide-id": "b", "layout": "title", "title": "B"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert [s.slide_id for s in parse_slides_yaml(p)] == ["a", "b"]


def test_parse_slides_yaml_rejects_duplicates(tmp_path: Path):
    p = tmp_path / "slides.yaml"
    p.write_text(
        "- slide-id: a\n  layout: title\n  title: A\n"
        "- slide-id: a\n  layout: title\n  title: B\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_slides_yaml(p)


def test_load_presentation_prefers_yaml(tmp_path: Path):
    _write_min_yaml_project(tmp_path)
    pres = load_presentation(tmp_path)
    assert [s.slide_id for s in pres.slides] == ["title", "thanks"]


def test_selections_yaml_round_trip(tmp_path: Path):
    _write_min_yaml_project(tmp_path)
    pres = load_presentation(tmp_path)
    pres.selections["title"] = Selection(model="gpt-image-1", variation=2, instance=1)
    save_selections(pres.selections_path, pres.selections)
    assert pres.selections_path.name == "selections.yaml"
    loaded = yaml.safe_load(pres.selections_path.read_text(encoding="utf-8"))
    assert loaded["title"] == {"model": "gpt-image-1", "variation": 2, "instance": 1}


def test_slides_to_yaml_text_is_human_readable(tmp_path: Path):
    _write_min_yaml_project(tmp_path)
    slides = parse_slides_yaml(tmp_path / "slides.yaml")
    text = slides_to_yaml_text(slides)
    # `slide-id` first per top-level entry, no Python-specific tags, unicode kept.
    assert "slide-id: title" in text
    assert "!!python" not in text


def test_migrate_command_converts_legacy_files(tmp_path: Path, monkeypatch):
    from click.testing import CliRunner

    folder = tmp_path / "legacy"
    folder.mkdir()
    (folder / "story.md").write_text("# story\n", encoding="utf-8")
    (folder / "slides.md").write_text(
        "---\nslide-id: only\nlayout: title\ntitle: Only\n---\n",
        encoding="utf-8",
    )
    (folder / "selections.json").write_text(
        json.dumps(
            {"only": {"model": "gpt-image-1", "variation": 1, "instance": 0}}
        ),
        encoding="utf-8",
    )
    (folder / "images.yaml").write_text("images: []\n", encoding="utf-8")
    (folder / "theme.yaml").write_text("template: null\nlayouts: {}\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(cli_main, ["migrate", str(folder)])
    assert res.exit_code == 0, res.output
    assert (folder / "slides.yaml").exists()
    assert (folder / "selections.yaml").exists()
    assert not (folder / "slides.md").exists()
    assert not (folder / "selections.json").exists()
    # Round-trip the migrated file.
    pres = load_presentation(folder)
    assert pres.slides[0].title == "Only"
    assert pres.selections["only"].model == "gpt-image-1"


def test_migrate_keep_old_preserves_originals(tmp_path: Path):
    from click.testing import CliRunner

    folder = tmp_path / "legacy2"
    folder.mkdir()
    (folder / "story.md").write_text("# story\n", encoding="utf-8")
    (folder / "slides.md").write_text(
        "---\nslide-id: a\nlayout: title\ntitle: A\n---\n",
        encoding="utf-8",
    )
    (folder / "images.yaml").write_text("images: []\n", encoding="utf-8")
    (folder / "theme.yaml").write_text("template: null\nlayouts: {}\n", encoding="utf-8")

    res = CliRunner().invoke(cli_main, ["migrate", str(folder), "--keep-old"])
    assert res.exit_code == 0
    assert (folder / "slides.md").exists()
    assert (folder / "slides.yaml").exists()
