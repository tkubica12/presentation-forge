"""`forge` CLI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from . import builder, spec
from .slides_parser import slides_to_yaml_text
from .spec import Selection, save_selections


SKILL_DIR = Path(__file__).resolve().parents[2]  # skills/presentation-forge/
TEMPLATES_DIR = SKILL_DIR / "src" / "presentation_forge" / "templates"


def _split_only(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


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
    click.echo(
        "Next: edit story.md, slides.yaml, images.yaml, theme.yaml, then `forge validate`."
    )


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
@click.option("--only", "only", default=None,
              help="Comma-separated image_ref names to restrict generation to.")
def images(folder: Path, parallelism: int | None, only: str | None) -> None:
    """Run the sibling image-generator skill (no PPTX rendering)."""
    pres = spec.load_presentation(folder)
    builder.validate(pres)
    builder.run_images(pres, parallelism=parallelism, only=_split_only(only))


@main.command(name="regen-image")
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("image_ref")
def regen_image(folder: Path, image_ref: str) -> None:
    """Wipe the cache for IMAGE_REF and regenerate it from scratch."""
    pres = spec.load_presentation(folder)
    builder.validate(pres)
    builder.regenerate_image(pres, image_ref)


@main.command(name="images-status")
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
def images_status_cmd(folder: Path) -> None:
    """Per image_ref: how many PNGs are on disk vs expected."""
    pres = spec.load_presentation(folder)
    rows = builder.images_status(pres)
    if not rows:
        click.echo("no image briefs.")
        return
    click.echo(f"{'image_ref':<32} {'pngs':>6} {'per-model':>10}  models")
    click.echo("-" * 70)
    for r in rows:
        marker = "✓" if r["complete"] else " "
        models = ",".join(r["models"]) or "-"
        click.echo(
            f"{marker} {r['image_ref']:<30} {r['pngs_found']:>6} "
            f"{r['expected_per_model']:>10}  {models}"
        )


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--draft/--no-draft", default=True)
@click.option("--final/--no-final", default=True)
@click.option("--skip-images", "--text-only", "skip_images", is_flag=True,
              help="Skip image generation entirely (text-only iteration). "
                   "Reuses any PNGs already on disk.")
@click.option("--only", "only", default=None,
              help="Comma-separated image_ref names; restrict image generation "
                   "to these refs (other refs reuse cached PNGs). Implies "
                   "--skip-images is OFF.")
def build(folder: Path, draft: bool, final: bool, skip_images: bool,
          only: str | None) -> None:
    """Build draft.pptx and/or final.pptx (default: both).

    Common modes:

      forge build <folder>                          # full build, image-gen + render
      forge build <folder> --skip-images            # text-only iteration
      forge build <folder> --only hero,cover        # regen images for two refs only
    """
    pres = spec.load_presentation(folder)
    warnings = builder.validate(pres)
    for w in warnings:
        click.echo(f"  warning: {w}", err=True)
    out = builder.build(
        pres, draft=draft, final=final,
        run_image_gen=not skip_images,
        only=_split_only(only),
    )
    click.echo(json.dumps({k: str(v) for k, v in out.items()}, indent=2))


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("slide_id")
@click.argument("model")
@click.argument("variation", type=int)
@click.argument("instance", type=int)
def select(folder: Path, slide_id: str, model: str, variation: int, instance: int) -> None:
    """Set selections[slide_id] = {model, variation, instance}."""
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


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--keep-old/--delete-old", default=False,
              help="Keep slides.md / selections.json after migration (default: delete).")
def migrate(folder: Path, keep_old: bool) -> None:
    """Migrate a legacy folder (slides.md + selections.json) to the
    unified YAML format (slides.yaml + selections.yaml).

    Idempotent: if the new files already exist they are not overwritten.
    """
    folder = folder.resolve()
    slides_md = folder / "slides.md"
    slides_yaml = folder / "slides.yaml"
    sel_json = folder / "selections.json"
    sel_yaml = folder / "selections.yaml"

    actions: list[str] = []

    if slides_yaml.exists():
        actions.append(f"slides.yaml already exists; skipping slides migration")
    elif slides_md.exists():
        from .slides_parser import parse_slides_md
        slides = parse_slides_md(slides_md)
        slides_yaml.write_text(slides_to_yaml_text(slides), encoding="utf-8")
        actions.append(f"wrote {slides_yaml.name} ({len(slides)} slides)")
        if not keep_old:
            slides_md.unlink()
            actions.append(f"deleted {slides_md.name}")
    else:
        actions.append("no slides.md or slides.yaml found")

    if sel_yaml.exists():
        actions.append("selections.yaml already exists; skipping selections migration")
    elif sel_json.exists():
        data = json.loads(sel_json.read_text(encoding="utf-8") or "{}")
        sel_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        actions.append(f"wrote {sel_yaml.name} ({len(data)} entries)")
        if not keep_old:
            sel_json.unlink()
            actions.append(f"deleted {sel_json.name}")
    else:
        actions.append("no selections.json or selections.yaml found")

    for a in actions:
        click.echo(a)
    click.echo("done.")


if __name__ == "__main__":
    main()
