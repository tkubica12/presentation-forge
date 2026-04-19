"""Build orchestration: validate spec, run image-generator, render PPTX(s)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import render_adapter
from .layouts import REQUIRED_FIELDS
from .spec import Presentation
from .state import State, hash_slide, hash_text


SKILL_DIR = Path(__file__).resolve().parents[2]  # skills/presentation-forge/
SKILLS_ROOT = SKILL_DIR.parent  # skills/
IMAGE_GENERATOR_DIR = SKILLS_ROOT / "image-generator"
PPTX_RENDER_DIR = SKILLS_ROOT / "pptx-render"
BUILD_DECK_SCRIPT = PPTX_RENDER_DIR / "scripts" / "build_deck.py"


class ValidationError(Exception):
    pass


def validate(pres: Presentation) -> list[str]:
    """Return list of validation warnings; raise on hard errors."""
    warnings: list[str] = []
    image_names = pres.image_names_in_yaml()

    for slide in pres.slides:
        # image_ref must resolve
        if slide.image_ref and slide.image_ref not in image_names:
            raise ValidationError(
                f"slide {slide.slide_id!r}: image_ref {slide.image_ref!r} "
                f"not found in images.yaml"
            )
        # required fields per layout — already checked at parse, double-check
        missing = REQUIRED_FIELDS[slide.layout] - set(slide.raw.keys())
        if missing:
            raise ValidationError(
                f"slide {slide.slide_id!r}: missing required fields {sorted(missing)}"
            )

    # Theme template, if specified, must exist
    if pres.theme.template and not pres.theme.template.exists():
        raise ValidationError(
            f"theme.yaml template path does not resolve: {pres.theme.template}"
        )

    # Selections referencing files that don't exist (yet) — warn only.
    for slide in pres.slides:
        sel = pres.selections.get(slide.slide_id)
        if sel is None or not slide.image_ref:
            continue
        path = (
            pres.images_dir / slide.image_ref / sel.model.lower()
            / sel.filename(slide.image_ref)
        )
        if not path.exists():
            warnings.append(
                f"selection for {slide.slide_id!r} points at missing file: {path}"
            )

    return warnings


def _find_uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise FileNotFoundError("`uv` not found in PATH; install uv to run sub-skills")
    return uv


def run_images(pres: Presentation, *, parallelism: int | None = None) -> None:
    """Shell out to the sibling image-generator skill."""
    if not IMAGE_GENERATOR_DIR.exists():
        raise FileNotFoundError(
            f"sibling image-generator skill not found at {IMAGE_GENERATOR_DIR}. "
            f"Install it with: gh skill install tkubica12/presentation-forge image-generator"
        )
    uv = _find_uv()
    cmd = [
        uv, "--directory", str(IMAGE_GENERATOR_DIR), "run", "generate-images",
        str(pres.images_yaml_path),
        "--output-dir", str(pres.images_dir),
    ]
    if parallelism is not None:
        cmd.extend(["--parallelism", str(parallelism)])
    print(f"$ {' '.join(cmd)}", flush=True)
    rc = subprocess.call(cmd, env=os.environ.copy())
    if rc != 0:
        raise RuntimeError(f"image-generator exited with code {rc}")


def _render_one(pres: Presentation, *, mode: str, output: Path) -> Path:
    """Materialize hve-core workspace and shell out to its build_deck.py."""
    if not BUILD_DECK_SCRIPT.exists():
        raise FileNotFoundError(
            f"sibling pptx-render skill not found at {PPTX_RENDER_DIR}. "
            f"It should be vendored at skills/pptx-render/."
        )
    workdir = pres.build_dir / f"_hve_{mode}"
    paths = render_adapter.materialize_workspace(pres, workdir=workdir, mode=mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    uv = _find_uv()
    cmd = [
        uv, "--directory", str(PPTX_RENDER_DIR), "run",
        "python", str(BUILD_DECK_SCRIPT),
        "--content-dir", str(paths.content_dir),
        "--style", str(paths.style_path),
        "--output", str(output),
    ]
    if paths.template_path is not None:
        cmd.extend(["--template", str(paths.template_path)])
    print(f"$ {' '.join(cmd)}", flush=True)
    rc = subprocess.call(cmd, env=os.environ.copy())
    if rc != 0:
        raise RuntimeError(f"build_deck.py exited with code {rc}")
    if not output.exists():
        raise RuntimeError(f"build_deck.py did not produce expected output: {output}")
    return output


def build(pres: Presentation, *, draft: bool = True, final: bool = True,
          run_image_gen: bool = True) -> dict[str, Path]:
    """Run the full build. Returns paths of generated artifacts."""
    if run_image_gen:
        run_images(pres)
    pres.build_dir.mkdir(parents=True, exist_ok=True)
    state = State.load(pres.state_path)

    out: dict[str, Path] = {}
    if draft:
        out["draft"] = _render_one(pres, mode="draft", output=pres.draft_pptx)
        for slide in pres.slides:
            state.record_slide(slide.slide_id, hash_slide(slide), kind="draft")
    if final:
        out["final"] = _render_one(pres, mode="final", output=pres.final_pptx)
        for slide in pres.slides:
            state.record_slide(slide.slide_id, hash_slide(slide), kind="final")

    state.images.setdefault("yaml_hash", hash_text(
        pres.images_yaml_path.read_text(encoding="utf-8")
    ))
    state.save(pres.state_path)
    return out


def status(pres: Presentation) -> list[dict]:
    """Per-slide summary used by `forge status`."""
    state = State.load(pres.state_path)
    out: list[dict] = []
    for slide in pres.slides:
        h = hash_slide(slide)
        prev = state.slides.get(slide.slide_id, {})
        sel = pres.selections.get(slide.slide_id)
        out.append({
            "slide_id": slide.slide_id,
            "layout": slide.layout.value,
            "image_ref": slide.image_ref,
            "selection": (
                f"{sel.model} v{sel.variation:02d} i{sel.instance:02d}"
                if sel else None
            ),
            "changed_since_last_build": prev.get("content_hash") != h if prev else True,
            "last_built": prev.get("last_built_final") or prev.get("last_built_draft"),
        })
    return out
