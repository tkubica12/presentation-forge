"""Tests for builder helpers added in the YAML/--only/lock-fallback rework."""
from __future__ import annotations

from pathlib import Path

import pytest

from presentation_forge import builder
from presentation_forge.builder import (
    _alternate_output,
    _is_locked,
    images_status,
)
from presentation_forge.spec import load_presentation


def _write_min_project(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.md").write_text("# s\n", encoding="utf-8")
    (folder / "slides.yaml").write_text(
        "- slide-id: a\n  layout: image-single\n  title: A\n  image_ref: alpha\n"
        "- slide-id: b\n  layout: image-single\n  title: B\n  image_ref: beta\n",
        encoding="utf-8",
    )
    (folder / "images.yaml").write_text(
        "models: [mai-image-2]\n"
        "variations_count: 2\n"
        "instances_per_prompt: 1\n"
        "images:\n"
        "  - name: alpha\n    description: A\n"
        "  - name: beta\n    description: B\n",
        encoding="utf-8",
    )
    (folder / "theme.yaml").write_text("template: null\nlayouts: {}\n", encoding="utf-8")


def test_alternate_output_picks_unique_sibling(tmp_path: Path):
    target = tmp_path / "final.pptx"
    target.write_bytes(b"x")
    alt = _alternate_output(target)
    assert alt.name == "final-updated.pptx"
    # Even if the candidate exists (but is not "locked"), we still return it
    # — the caller uses it as a write target.
    alt.write_bytes(b"x")
    assert _alternate_output(target).name == "final-updated.pptx"


def test_is_locked_returns_false_for_missing(tmp_path: Path):
    assert _is_locked(tmp_path / "nope.pptx") is False


def test_run_images_only_unknown_ref_raises(tmp_path: Path, monkeypatch):
    _write_min_project(tmp_path)
    pres = load_presentation(tmp_path)
    monkeypatch.setattr(builder, "_find_uv", lambda: "uv")
    with pytest.raises(ValueError, match="unknown"):
        builder.run_images(pres, only=["bogus"])


def test_run_images_only_filters_yaml(tmp_path: Path, monkeypatch):
    """--only writes a temp YAML containing only the requested image_ref."""
    _write_min_project(tmp_path)
    pres = load_presentation(tmp_path)
    monkeypatch.setattr(builder, "_find_uv", lambda: "uv")

    captured = {}

    def fake_call(cmd, env=None):
        # The image-generator command should reference the temp YAML, not
        # the original.
        yaml_arg = cmd[cmd.index("generate-images") + 1]
        captured["yaml"] = Path(yaml_arg)
        captured["text"] = captured["yaml"].read_text(encoding="utf-8")
        return 0

    monkeypatch.setattr(builder.subprocess, "call", fake_call)
    builder.run_images(pres, only=["alpha"])
    assert captured["yaml"] != pres.images_yaml_path
    assert "alpha" in captured["text"] and "beta" not in captured["text"]


def test_images_status_reports_zero_when_nothing_generated(tmp_path: Path):
    _write_min_project(tmp_path)
    pres = load_presentation(tmp_path)
    rows = images_status(pres)
    refs = [r["image_ref"] for r in rows]
    assert refs == ["alpha", "beta"]
    for r in rows:
        assert r["pngs_found"] == 0
        assert r["expected_per_model"] == 2
        assert r["complete"] is False


def test_images_status_counts_pngs(tmp_path: Path):
    _write_min_project(tmp_path)
    pres = load_presentation(tmp_path)
    pres.images_dir.mkdir(parents=True, exist_ok=True)
    model_dir = pres.images_dir / "alpha" / "mai-image-2"
    model_dir.mkdir(parents=True)
    (model_dir / "alpha_v00_i00.png").write_bytes(b"fakepng")
    (model_dir / "alpha_v01_i00.png").write_bytes(b"fakepng")
    rows = {r["image_ref"]: r for r in images_status(pres)}
    assert rows["alpha"]["pngs_found"] == 2
    assert rows["alpha"]["complete"] is True
    assert rows["beta"]["pngs_found"] == 0
