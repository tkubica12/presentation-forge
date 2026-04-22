"""Top-level spec loader: presentation folder -> in-memory model."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .slides_parser import Slide, parse_slides_md, parse_slides_yaml


def _resolve_user_path(base: Path, value: object) -> Path | None:
    if value in (None, ""):
        return None
    text = str(value).replace("\\", "/")
    return (base / Path(text)).resolve()


@dataclass
class Theme:
    template: Path | None = None
    fonts: dict[str, str] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    logo: Path | None = None
    # Mapping from our logical layout name (Layout enum value) to the
    # PowerPoint slide-layout name (or integer index) inside `template`.
    # Consumed by hve-core's `build_deck.py` via `style.yaml`.
    layouts: dict[str, str | int] = field(default_factory=dict)
    # Optional file-property metadata for the produced PPTX.
    metadata: dict[str, str] = field(default_factory=dict)
    # Optional defaults block forwarded to hve-core's `style.yaml`.
    defaults: dict[str, Any] = field(default_factory=dict)
    # Optional per-layout background colour overrides (layout name -> hex).
    layout_backgrounds: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], base: Path) -> "Theme":
        tpl = data.get("template")
        logo = data.get("logo")
        layouts_raw = data.get("layouts") or {}
        if not isinstance(layouts_raw, dict):
            raise ValueError("theme.yaml: `layouts` must be a mapping")
        layouts: dict[str, str | int] = {}
        for k, v in layouts_raw.items():
            if not isinstance(k, str):
                raise ValueError(f"theme.yaml layouts: non-string key {k!r}")
            if not isinstance(v, (str, int)):
                raise ValueError(
                    f"theme.yaml layouts[{k!r}]: value must be string or int"
                )
            layouts[k] = v
        metadata_raw = data.get("metadata") or {}
        if not isinstance(metadata_raw, dict):
            raise ValueError("theme.yaml: `metadata` must be a mapping")
        defaults_raw = data.get("defaults") or {}
        if not isinstance(defaults_raw, dict):
            raise ValueError("theme.yaml: `defaults` must be a mapping")
        bg_raw = data.get("layout_backgrounds") or {}
        if not isinstance(bg_raw, dict):
            raise ValueError("theme.yaml: `layout_backgrounds` must be a mapping")
        return cls(
            template=_resolve_user_path(base, tpl),
            fonts=dict(data.get("fonts") or {}),
            colors=dict(data.get("colors") or {}),
            logo=_resolve_user_path(base, logo),
            layouts=layouts,
            metadata={str(k): str(v) for k, v in metadata_raw.items()},
            defaults=dict(defaults_raw),
            layout_backgrounds={str(k): str(v) for k, v in bg_raw.items()},
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
        # Prefer the new YAML format. Fall back to legacy JSON only if it
        # actually exists. New projects always write YAML.
        json_path = self.folder / "selections.json"
        yaml_path = self.folder / "selections.yaml"
        if yaml_path.exists():
            return yaml_path
        if json_path.exists():
            return json_path
        return yaml_path

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
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        raw = yaml.safe_load(text) or {}
    else:
        raw = json.loads(text)
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
    if path.suffix.lower() in (".yaml", ".yml"):
        path.write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def load_presentation(folder: Path) -> Presentation:
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"not a directory: {folder}")

    story = folder / "story.md"
    slides_yaml = folder / "slides.yaml"
    slides_md = folder / "slides.md"
    images_yaml = folder / "images.yaml"
    theme_yaml = folder / "theme.yaml"

    # Prefer YAML for slides + selections; fall back to legacy formats.
    if slides_yaml.exists():
        slides_path = slides_yaml
    elif slides_md.exists():
        slides_path = slides_md
    else:
        raise FileNotFoundError(
            f"missing required slides file: {slides_yaml} (or legacy {slides_md})"
        )

    for required in (images_yaml, theme_yaml):
        if not required.exists():
            raise FileNotFoundError(f"missing required file: {required}")

    if slides_path.suffix == ".yaml":
        slides = parse_slides_yaml(slides_path)
    else:
        slides = parse_slides_md(slides_path)

    images_data = yaml.safe_load(images_yaml.read_text(encoding="utf-8")) or {}
    theme = Theme.from_dict(yaml.safe_load(theme_yaml.read_text(encoding="utf-8")) or {}, folder)

    sel_yaml = folder / "selections.yaml"
    sel_json = folder / "selections.json"
    if sel_yaml.exists():
        sels = _load_selections(sel_yaml)
    elif sel_json.exists():
        sels = _load_selections(sel_json)
    else:
        sels = {}

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
