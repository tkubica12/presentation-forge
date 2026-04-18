"""Top-level spec loader: presentation folder -> in-memory model."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .slides_parser import Slide, parse_slides_md


@dataclass
class Theme:
    template: Path | None = None
    fonts: dict[str, str] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    logo: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], base: Path) -> "Theme":
        tpl = data.get("template")
        logo = data.get("logo")
        return cls(
            template=(base / tpl).resolve() if tpl else None,
            fonts=dict(data.get("fonts") or {}),
            colors=dict(data.get("colors") or {}),
            logo=(base / logo).resolve() if logo else None,
        )


@dataclass
class Selection:
    model: str
    variation: int
    instance: int

    def filename(self, image_ref: str) -> str:
        return f"{image_ref}_v{self.variation:02d}_i{self.instance:02d}.png"


@dataclass
class Presentation:
    folder: Path
    slides: list[Slide]
    images_yaml_path: Path
    images_yaml_data: dict[str, Any]
    theme: Theme
    selections: dict[str, Selection | None]
    story_md_path: Path

    @property
    def build_dir(self) -> Path:
        return self.folder / "build"

    @property
    def images_dir(self) -> Path:
        return self.build_dir / "images"

    @property
    def state_path(self) -> Path:
        return self.build_dir / "state.json"

    @property
    def selections_path(self) -> Path:
        return self.folder / "selections.json"

    @property
    def draft_pptx(self) -> Path:
        return self.build_dir / "draft.pptx"

    @property
    def final_pptx(self) -> Path:
        return self.build_dir / "final.pptx"

    def image_names_in_yaml(self) -> set[str]:
        return {entry["name"] for entry in self.images_yaml_data.get("images", [])}


def _load_selections(path: Path) -> dict[str, Selection | None]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Selection | None] = {}
    for sid, val in raw.items():
        if val is None:
            out[sid] = None
        else:
            out[sid] = Selection(
                model=val["model"],
                variation=int(val["variation"]),
                instance=int(val["instance"]),
            )
    return out


def save_selections(path: Path, selections: dict[str, Selection | None]) -> None:
    out: dict[str, Any] = {}
    for sid, sel in selections.items():
        if sel is None:
            out[sid] = None
        else:
            out[sid] = {
                "model": sel.model,
                "variation": sel.variation,
                "instance": sel.instance,
            }
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def load_presentation(folder: Path) -> Presentation:
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"not a directory: {folder}")

    story = folder / "story.md"
    slides_md = folder / "slides.md"
    images_yaml = folder / "images.yaml"
    theme_yaml = folder / "theme.yaml"
    selections = folder / "selections.json"

    for required in (slides_md, images_yaml, theme_yaml):
        if not required.exists():
            raise FileNotFoundError(f"missing required file: {required}")

    slides = parse_slides_md(slides_md)
    images_data = yaml.safe_load(images_yaml.read_text(encoding="utf-8")) or {}
    theme = Theme.from_dict(yaml.safe_load(theme_yaml.read_text(encoding="utf-8")) or {}, folder)
    sels = _load_selections(selections)

    # Initialize null selections for any slide-id that doesn't have one yet.
    for slide in slides:
        sels.setdefault(slide.slide_id, None)

    return Presentation(
        folder=folder,
        slides=slides,
        images_yaml_path=images_yaml,
        images_yaml_data=images_data,
        theme=theme,
        selections=sels,
        story_md_path=story,
    )
