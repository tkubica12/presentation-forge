"""Adapter: presentation-forge model -> hve-core content tree.

The vendored `microsoft/hve-core` PowerPoint skill at
`skills/pptx-render/` consumes a folder layout shaped like:

    content/
      global/style.yaml
      slide-001/
        content.yaml
        images/<png files used by this slide>
      slide-002/
        ...

Our authoring layer is `slides.md` + `theme.yaml` + `selections.json`
(plus generated PNGs under `<folder>/build/images/<image_ref>/<model>/...`).

`materialize_workspace` writes the upstream-shaped content tree into a
build-scratch directory and returns the paths needed to invoke
`build_deck.py`. Two flavours are supported:

  * ``draft``  — one slide per existing image variant (with a label
                 suffix) so the user can pick a winner, plus textual
                 slides verbatim
  * ``final``  — one slide per spec slide, using the user's selection
                 (or a placeholder note for slides whose image is
                 missing or unselected)

Each slide is rendered onto a named template layout via the mapping in
`theme.yaml.layouts`; placeholders are filled where the layout has them,
and remaining content (images, decorative elements) is emitted as
hve-core ``elements:``.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .layouts import Layout
from .slides_parser import Slide
from .spec import Presentation, Selection, Theme


# Default logical-name -> Microsoft Azure template layout-name mapping.
# Used as a fallback when theme.yaml does not provide its own `layouts:`
# block. Picks layouts that exist in
# .templates/Microsoft-Azure-PowerPoint-Template-2604.potx and play the
# role expected by each Layout enum value.
DEFAULT_AZURE_LAYOUTS: dict[str, str] = {
    Layout.TITLE.value: "Title Slide 1",
    Layout.SECTION_DIVIDER.value: "Section Slide 1",
    Layout.BULLETS.value: "Title and Content",
    Layout.BULLETS_WITH_IMAGE.value: "Title & Text Side By Side 1",
    Layout.FULL_BLEED_IMAGE.value: "Photo full bleed lower title",
    Layout.TWO_COLUMN.value: "Two Column Bullet text",
    Layout.QUOTE.value: "Quote",
    Layout.COMPARISON.value: "Two Column Bullet text",
    Layout.IMAGE_GRID.value: "Three picture content",
    Layout.APPENDIX_REFERENCES.value: "Title & Non-bulleted text",
}


# Per-layout placeholder index conventions for the Azure template.
# Discovered empirically by inspecting `.templates/...potx`. The fields
# describe which placeholder index inside the layout receives which kind
# of content. None means "no placeholder of that role on this layout".
@dataclass(frozen=True)
class PlaceholderRoles:
    title: int | None = 0
    body: int | None = None       # primary text body / left column
    secondary: int | None = None  # right column or attribution
    picture: int | None = None    # PICTURE placeholder, if any


DEFAULT_PLACEHOLDER_ROLES: dict[str, PlaceholderRoles] = {
    Layout.TITLE.value: PlaceholderRoles(title=0, body=12),
    Layout.SECTION_DIVIDER.value: PlaceholderRoles(title=0),
    Layout.BULLETS.value: PlaceholderRoles(title=0, body=10),
    Layout.BULLETS_WITH_IMAGE.value: PlaceholderRoles(title=0, body=11),
    Layout.FULL_BLEED_IMAGE.value: PlaceholderRoles(title=0, picture=10),
    Layout.TWO_COLUMN.value: PlaceholderRoles(title=0, body=12, secondary=13),
    Layout.QUOTE.value: PlaceholderRoles(title=0, body=12, secondary=18),
    Layout.COMPARISON.value: PlaceholderRoles(title=0, body=12, secondary=13),
    Layout.IMAGE_GRID.value: PlaceholderRoles(title=0),
    Layout.APPENDIX_REFERENCES.value: PlaceholderRoles(title=0, body=10),
}


# Slide canvas constants (16:9 EMU dimensions of the Azure template).
SLIDE_W = 13.333
SLIDE_H = 7.5


def _placeholder_value(text: str | None) -> str | None:
    """Normalize text destined for a placeholder. Empty -> None."""
    if text is None:
        return None
    s = text.strip()
    return s or None


def _bullets_to_lines(bullets: list[str]) -> list[str] | None:
    items = [b.strip() for b in (bullets or []) if b and b.strip()]
    return items or None


def _resolve_selected_image(pres: Presentation, slide: Slide) -> Path | None:
    if not slide.image_ref:
        return None
    sel = pres.selections.get(slide.slide_id)
    if sel is None:
        return None
    return (
        pres.images_dir / slide.image_ref / sel.model.lower()
        / sel.filename(slide.image_ref)
    )


_VARIANT_RE = re.compile(r"^(?P<ref>.+)_v(?P<v>\d+)_i(?P<i>\d+)\.png$")


def _list_variants(
    pres: Presentation, slide: Slide
) -> list[tuple[str, int, int, Path]]:
    out: list[tuple[str, int, int, Path]] = []
    if not slide.image_ref:
        return out
    base = pres.images_dir / slide.image_ref
    if not base.exists():
        return out
    for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for png in sorted(model_dir.iterdir()):
            m = _VARIANT_RE.match(png.name)
            if m and m.group("ref") == slide.image_ref:
                out.append(
                    (model_dir.name, int(m.group("v")), int(m.group("i")), png)
                )
    return out


def _picture_placeholder_dims(
    template_path: Path | None, layout_name: str, idx: int
) -> tuple[float, float, float, float] | None:
    """Look up the inch coordinates of a picture placeholder in *template_path*.

    Returns (left, top, width, height) in inches, or ``None`` if the layout
    or placeholder cannot be found. We use this to draw an explicit ``image``
    element where the layout would normally place a picture, since hve-core's
    placeholder code does not insert pictures into picture-placeholders.
    """
    if template_path is None or not template_path.exists():
        return None
    # Local import keeps `python-pptx` out of the import chain when callers
    # only need the textual transformation.
    from pptx import Presentation as PptxPresentation
    from pptx.util import Emu

    prs = PptxPresentation(str(template_path))
    for layout in prs.slide_layouts:
        if layout.name != layout_name:
            continue
        for ph in layout.placeholders:
            if ph.placeholder_format.idx == idx:
                return (
                    Emu(ph.left).inches,
                    Emu(ph.top).inches,
                    Emu(ph.width).inches,
                    Emu(ph.height).inches,
                )
    return None


# ---------------------------------------------------------------------------
# Per-slide content.yaml emission
# ---------------------------------------------------------------------------


def slide_to_content(
    slide: Slide,
    *,
    image_paths: list[Path] | None = None,
    label_suffix: str | None = None,
    template_path: Path | None = None,
    layouts_map: dict[str, str | int] | None = None,
    images_dir_name: str = "images",
) -> dict[str, Any]:
    """Convert a single :class:`Slide` to an hve-core ``content.yaml`` dict.

    *image_paths* are filenames already copied into the slide's ``images/``
    subfolder; only their basenames are referenced. *label_suffix*, when
    provided, is appended to the slide's title (used by draft renders to
    distinguish per-variant slides).
    """
    image_paths = image_paths or []
    layouts_map = layouts_map or {}
    layout_value = slide.layout.value
    title_text = slide.title
    if label_suffix and title_text:
        title_text = f"{title_text} {label_suffix}"
    elif label_suffix and not title_text:
        title_text = label_suffix.strip()

    roles = DEFAULT_PLACEHOLDER_ROLES.get(layout_value, PlaceholderRoles())
    placeholders: dict[int, str | list[str]] = {}
    elements: list[dict[str, Any]] = []

    # Title placeholder
    if roles.title is not None:
        v = _placeholder_value(title_text)
        if v is not None:
            placeholders[roles.title] = v

    # Body / bullets / quote text routing per layout
    if slide.layout is Layout.TITLE:
        sub = _placeholder_value(slide.subtitle)
        if sub and roles.body is not None:
            placeholders[roles.body] = sub

    elif slide.layout is Layout.SECTION_DIVIDER:
        # Section layouts have only a title placeholder; subtitle, if any,
        # is rendered as a small textbox below the title.
        sub = _placeholder_value(slide.subtitle)
        if sub:
            elements.append({
                "type": "textbox",
                "left": 0.8,
                "top": 4.6,
                "width": SLIDE_W - 1.6,
                "height": 0.7,
                "text": sub,
                "font_size": 22,
                "font_italic": True,
            })

    elif slide.layout in (Layout.BULLETS, Layout.APPENDIX_REFERENCES):
        body_lines = _bullets_to_lines(slide.bullets) or (
            [slide.body.strip()] if slide.body and slide.body.strip() else None
        )
        if body_lines and roles.body is not None:
            placeholders[roles.body] = body_lines

    elif slide.layout is Layout.BULLETS_WITH_IMAGE:
        body_lines = _bullets_to_lines(slide.bullets)
        if body_lines and roles.body is not None:
            placeholders[roles.body] = body_lines
        # Image element: half-width on the side opposite the text.
        if image_paths:
            position = (slide.image_position or "right").lower()
            half_w = (SLIDE_W - 1.6 - 0.4) / 2
            top = 1.7
            height = SLIDE_H - top - 0.6
            if position == "left":
                left = 0.8
            else:
                left = 0.8 + half_w + 0.4
            elements.append({
                "type": "image",
                "path": f"{images_dir_name}/{image_paths[0].name}",
                "left": left,
                "top": top,
                "width": half_w,
                "height": height,
            })

    elif slide.layout is Layout.FULL_BLEED_IMAGE:
        if image_paths:
            dims = _picture_placeholder_dims(
                template_path,
                layouts_map.get(layout_value, DEFAULT_AZURE_LAYOUTS[layout_value])
                if isinstance(
                    layouts_map.get(layout_value, DEFAULT_AZURE_LAYOUTS[layout_value]),
                    str,
                )
                else DEFAULT_AZURE_LAYOUTS[layout_value],
                roles.picture if roles.picture is not None else 10,
            ) or (0.0, 0.0, SLIDE_W, SLIDE_H)
            left, top, w, h = dims
            elements.append({
                "type": "image",
                "path": f"{images_dir_name}/{image_paths[0].name}",
                "left": left,
                "top": top,
                "width": w,
                "height": h,
            })

    elif slide.layout in (Layout.TWO_COLUMN, Layout.COMPARISON):
        bullets = list(slide.bullets or [])
        # Even-index bullets -> left column; odd-index -> right column.
        left_col = [b for i, b in enumerate(bullets) if i % 2 == 0]
        right_col = [b for i, b in enumerate(bullets) if i % 2 == 1]
        left_lines = _bullets_to_lines(left_col)
        right_lines = _bullets_to_lines(right_col)
        if left_lines and roles.body is not None:
            placeholders[roles.body] = left_lines
        if right_lines and roles.secondary is not None:
            placeholders[roles.secondary] = right_lines

    elif slide.layout is Layout.QUOTE:
        body = (slide.body or "").strip()
        if body and roles.body is not None:
            placeholders[roles.body] = f"\u201c{body}\u201d"
        attribution = _placeholder_value(slide.subtitle)
        if attribution and roles.secondary is not None:
            placeholders[roles.secondary] = f"\u2014 {attribution}"

    elif slide.layout is Layout.IMAGE_GRID:
        # Up to 3 images laid out in equal thirds across the body.
        chosen = image_paths[:3]
        if chosen:
            top = 2.0
            gap = 0.2
            tile_w = (SLIDE_W - 1.6 - gap * (len(chosen) - 1)) / len(chosen)
            tile_h = SLIDE_H - top - 0.8
            for i, path in enumerate(chosen):
                elements.append({
                    "type": "image",
                    "path": f"{images_dir_name}/{path.name}",
                    "left": 0.8 + i * (tile_w + gap),
                    "top": top,
                    "width": tile_w,
                    "height": tile_h,
                })

    # Append the slide's own opt-in `extra_elements` passthrough. These are
    # spliced verbatim — agents/users own validity. Drawn last so they sit
    # on top of adapter-generated content.
    if slide.extra_elements:
        elements.extend(slide.extra_elements)

    content: dict[str, Any] = {
        "slide": 1,  # caller overrides
        "layout": layout_value,
    }
    if title_text:
        content["title"] = title_text
    if placeholders:
        # YAML emits int keys as integers; hve-core re-coerces via `int(idx_str)`.
        content["placeholders"] = {int(k): v for k, v in placeholders.items()}
    if elements:
        content["elements"] = elements
    if slide.notes:
        content["notes"] = slide.notes.strip()
    return content


# ---------------------------------------------------------------------------
# Workspace materialization
# ---------------------------------------------------------------------------


def _build_style(
    pres: Presentation, *, normalized_template_path: Path | None
) -> dict[str, Any]:
    style: dict[str, Any] = {
        "dimensions": {
            "width_inches": SLIDE_W,
            "height_inches": SLIDE_H,
            "format": "16:9",
        },
    }
    if normalized_template_path is not None:
        style["template"] = {
            "path": str(normalized_template_path),
            "preserve_dimensions": True,
        }
    layouts_map: dict[str, str | int] = dict(DEFAULT_AZURE_LAYOUTS)
    layouts_map.update(pres.theme.layouts or {})
    style["layouts"] = layouts_map
    if pres.theme.metadata:
        style["metadata"] = dict(pres.theme.metadata)
    if pres.theme.defaults:
        style["defaults"] = dict(pres.theme.defaults)
    if pres.theme.fonts:
        # Surface fonts under metadata so they end up in the produced PPTX
        # properties (informational; hve-core does not consume `fonts`).
        style.setdefault("metadata", {}).setdefault(
            "subject", style["metadata"].get("subject", "")
        )
    return style


@dataclass
class WorkspacePaths:
    """Result of :func:`materialize_workspace`."""

    workdir: Path
    content_dir: Path
    style_path: Path
    template_path: Path | None
    slide_dirs: list[Path]


def materialize_workspace(
    pres: Presentation,
    *,
    workdir: Path,
    mode: str,
) -> WorkspacePaths:
    """Materialize the full hve-core content tree under *workdir*.

    *mode* must be one of ``"draft"`` or ``"final"``. ``draft`` emits one
    slide per image variant for each image-bearing slide; ``final`` emits
    one slide per spec slide, using the user's current selection.

    The returned :class:`WorkspacePaths` is everything `build_deck.py`
    needs (``content_dir``, ``style_path``, optional ``template_path``).
    """
    if mode not in ("draft", "final"):
        raise ValueError(f"mode must be 'draft' or 'final', got {mode!r}")
    workdir = Path(workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    content_dir = workdir / "content"
    global_dir = content_dir / "global"
    global_dir.mkdir(parents=True)

    template_path: Path | None = None
    if pres.theme.template:
        from .template_utils import normalize_template_to_pptx

        normalized = workdir / "template.pptx"
        template_path = normalize_template_to_pptx(pres.theme.template, normalized)

    style = _build_style(pres, normalized_template_path=template_path)
    style_path = global_dir / "style.yaml"
    style_path.write_text(yaml.safe_dump(style, sort_keys=False), encoding="utf-8")

    slide_dirs: list[Path] = []
    slide_no = 0

    for slide in pres.slides:
        if mode == "draft" and slide.image_ref:
            variants = _list_variants(pres, slide)
            if not variants:
                slide_no += 1
                _emit_slide(
                    slide,
                    slide_no=slide_no,
                    content_dir=content_dir,
                    image_files=[],
                    label_suffix="(no images yet)",
                    template_path=template_path,
                    layouts_map=pres.theme.layouts,
                    slide_dirs=slide_dirs,
                )
                continue
            for i, (model, var, inst, src_path) in enumerate(variants, start=1):
                slide_no += 1
                suffix = (
                    f"\u2014 variant {i}/{len(variants)} "
                    f"({model} v{var:02d} i{inst:02d})"
                )
                _emit_slide(
                    slide,
                    slide_no=slide_no,
                    content_dir=content_dir,
                    image_files=[src_path],
                    label_suffix=suffix,
                    template_path=template_path,
                    layouts_map=pres.theme.layouts,
                    slide_dirs=slide_dirs,
                )
            continue

        # Final mode (or draft for textual slides): one slide.
        image_files: list[Path] = []
        if mode == "final" and slide.image_ref:
            sel_path = _resolve_selected_image(pres, slide)
            if sel_path and sel_path.exists():
                image_files = [sel_path]
            elif slide.layout is Layout.IMAGE_GRID:
                image_files = [p for *_, p in _list_variants(pres, slide)][:3]
        elif mode == "draft" and slide.layout is Layout.IMAGE_GRID:
            image_files = [p for *_, p in _list_variants(pres, slide)][:3]

        slide_no += 1
        _emit_slide(
            slide,
            slide_no=slide_no,
            content_dir=content_dir,
            image_files=image_files,
            label_suffix=None,
            template_path=template_path,
            layouts_map=pres.theme.layouts,
            slide_dirs=slide_dirs,
        )

    return WorkspacePaths(
        workdir=workdir,
        content_dir=content_dir,
        style_path=style_path,
        template_path=template_path,
        slide_dirs=slide_dirs,
    )


def _emit_slide(
    slide: Slide,
    *,
    slide_no: int,
    content_dir: Path,
    image_files: list[Path],
    label_suffix: str | None,
    template_path: Path | None,
    layouts_map: dict[str, str | int],
    slide_dirs: list[Path],
) -> None:
    slide_dir = content_dir / f"slide-{slide_no:03d}"
    images_dir = slide_dir / "images"
    slide_dir.mkdir(parents=True)
    copied: list[Path] = []
    if image_files:
        images_dir.mkdir(parents=True)
        for src in image_files:
            dst = images_dir / src.name
            shutil.copyfile(src, dst)
            copied.append(dst)

    content = slide_to_content(
        slide,
        image_paths=copied,
        label_suffix=label_suffix,
        template_path=template_path,
        layouts_map=layouts_map,
    )
    content["slide"] = slide_no
    (slide_dir / "content.yaml").write_text(
        yaml.safe_dump(content, sort_keys=False), encoding="utf-8"
    )
    slide_dirs.append(slide_dir)
