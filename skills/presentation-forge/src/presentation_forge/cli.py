"""`forge` CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import builder, spec
from .spec import Selection, save_selections


SKILL_DIR = Path(__file__).resolve().parents[2]  # skills/presentation-forge/
TEMPLATES_DIR = SKILL_DIR / "src" / "presentation_forge" / "templates"


@click.group()
def main() -> None:
    """presentation-forge — text-first presentation builder."""


@main.command()
@click.argument("parent", type=click.Path(file_okay=False, path_type=Path))
@click.argument("name")
def new(parent: Path, name: str) -> None:
    """Scaffold a new presentation folder under PARENT/NAME."""
    folder = (parent / name).resolve()
    if folder.exists():
        click.echo(f"refusing to overwrite existing folder: {folder}", err=True)
        sys.exit(2)
    folder.mkdir(parents=True)
    for src in TEMPLATES_DIR.glob("*.tmpl"):
        dst_name = src.name.removesuffix(".tmpl")
        (folder / dst_name).write_text(
            src.read_text(encoding="utf-8").replace("{{NAME}}", name),
            encoding="utf-8",
        )
    click.echo(f"created {folder}")
    click.echo("Next: edit story.md, slides.md, images.yaml, theme.yaml, then `forge validate`.")


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
def validate(folder: Path) -> None:
    """Lint a presentation folder."""
    pres = spec.load_presentation(folder)
    warnings = builder.validate(pres)
    click.echo(f"OK: {len(pres.slides)} slides, {len(pres.image_names_in_yaml())} image briefs.")
    for w in warnings:
        click.echo(f"  warning: {w}")


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--parallelism", type=int, default=None)
def images(folder: Path, parallelism: int | None) -> None:
    """Run the sibling image-generator skill (no PPTX rendering)."""
    pres = spec.load_presentation(folder)
    builder.validate(pres)
    builder.run_images(pres, parallelism=parallelism)


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--draft/--no-draft", default=True)
@click.option("--final/--no-final", default=True)
@click.option("--skip-images", is_flag=True, help="Skip image generation step")
def build(folder: Path, draft: bool, final: bool, skip_images: bool) -> None:
    """Build draft.pptx and/or final.pptx (default: both)."""
    pres = spec.load_presentation(folder)
    warnings = builder.validate(pres)
    for w in warnings:
        click.echo(f"  warning: {w}", err=True)
    out = builder.build(pres, draft=draft, final=final, run_image_gen=not skip_images)
    click.echo(json.dumps({k: str(v) for k, v in out.items()}, indent=2))


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("slide_id")
@click.argument("model")
@click.argument("variation", type=int)
@click.argument("instance", type=int)
def select(folder: Path, slide_id: str, model: str, variation: int, instance: int) -> None:
    """Set selections.json[slide_id] = {model, variation, instance}."""
    pres = spec.load_presentation(folder)
    if slide_id not in {s.slide_id for s in pres.slides}:
        click.echo(f"unknown slide-id: {slide_id}", err=True)
        sys.exit(2)
    pres.selections[slide_id] = Selection(model=model, variation=variation, instance=instance)
    save_selections(pres.selections_path, pres.selections)
    click.echo(f"updated {pres.selections_path}: {slide_id} -> {model} v{variation:02d} i{instance:02d}")


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
def status(folder: Path) -> None:
    """Per-slide status table."""
    pres = spec.load_presentation(folder)
    rows = builder.status(pres)
    click.echo(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    main()
