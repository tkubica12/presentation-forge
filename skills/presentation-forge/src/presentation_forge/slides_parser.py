"""Parse slides.md into structured Slide records."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .layouts import Layout, REQUIRED_FIELDS

SLIDE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Slide:
    slide_id: str
    layout: Layout
    title: str | None = None
    subtitle: str | None = None
    bullets: list[str] = field(default_factory=list)
    body: str | None = None
    image_ref: str | None = None
    image_position: str | None = None  # left | right | full
    notes: str | None = None
    # Optional passthrough: list of element dicts spliced verbatim into the
    # `elements:` array of the rendered hve-core content.yaml. Use this only
    # when the editorial layer (title/bullets/image_ref) cannot express the
    # one-off shape you need — see references/SLIDES_FORMAT.md.
    extra_elements: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_block(cls, data: dict[str, Any]) -> "Slide":
        sid = data.get("slide-id")
        if not isinstance(sid, str) or not SLIDE_ID_RE.match(sid):
            raise ValueError(
                f"slide-id must be kebab-case ASCII matching {SLIDE_ID_RE.pattern}, "
                f"got {sid!r}"
            )
        layout_raw = data.get("layout")
        try:
            layout = Layout(layout_raw)
        except ValueError as e:
            raise ValueError(
                f"slide {sid!r}: unknown layout {layout_raw!r}. "
                f"Valid: {[l.value for l in Layout]}"
            ) from e
        missing = REQUIRED_FIELDS[layout] - set(data.keys())
        # `bullets` field is required as a list with content
        if "bullets" in REQUIRED_FIELDS[layout]:
            b = data.get("bullets")
            if not isinstance(b, list) or not b:
                missing.add("bullets")
        if missing:
            raise ValueError(
                f"slide {sid!r} (layout {layout.value}): missing required fields {sorted(missing)}"
            )
        extra = data.get("extra_elements") or []
        if not isinstance(extra, list) or any(
            not isinstance(e, dict) for e in extra
        ):
            raise ValueError(
                f"slide {sid!r}: `extra_elements` must be a list of dicts"
            )
        return cls(
            slide_id=sid,
            layout=layout,
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            bullets=list(data.get("bullets") or []),
            body=data.get("body"),
            image_ref=data.get("image_ref"),
            image_position=data.get("image_position"),
            notes=data.get("notes"),
            extra_elements=list(extra),
            raw=data,
        )


def parse_slides_md(path: Path) -> list[Slide]:
    """Parse legacy slides.md.

    Format: each slide is a YAML frontmatter block delimited by lines of
    exactly three dashes (---). Empty lines between blocks are tolerated.
    """
    text = path.read_text(encoding="utf-8")
    # Split on lines that are exactly "---" (with optional surrounding whitespace).
    chunks = re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)
    slides: list[Slide] = []
    seen_ids: set[str] = set()
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            data = yaml.safe_load(chunk)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error in slide block:\n{chunk[:200]}\n\n{e}") from e
        if not isinstance(data, dict):
            # likely stray markdown body — skip
            continue
        if "slide-id" not in data:
            # not a slide block (e.g. a free-form note) — skip
            continue
        slide = Slide.from_block(data)
        if slide.slide_id in seen_ids:
            raise ValueError(f"duplicate slide-id {slide.slide_id!r}")
        seen_ids.add(slide.slide_id)
        slides.append(slide)
    if not slides:
        raise ValueError(f"no slides found in {path}")
    return slides


def parse_slides_yaml(path: Path) -> list[Slide]:
    """Parse slides.yaml — a top-level list of slide dicts.

    The schema for each entry is identical to a slides.md frontmatter
    block (slide-id, layout, title, bullets, body, image_ref, ...).
    A top-level mapping with a ``slides:`` key is also accepted, for
    forward-compatibility with future shared metadata.
    """
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error in {path}: {e}") from e
    if isinstance(data, dict) and "slides" in data:
        data = data["slides"]
    if data is None:
        raise ValueError(f"no slides found in {path}")
    if not isinstance(data, list):
        raise ValueError(
            f"{path}: expected a list of slide dicts at the top level "
            f"(or a mapping with `slides:` key)"
        )
    slides: list[Slide] = []
    seen_ids: set[str] = set()
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: every slide entry must be a mapping, got {entry!r}")
        slide = Slide.from_block(entry)
        if slide.slide_id in seen_ids:
            raise ValueError(f"duplicate slide-id {slide.slide_id!r}")
        seen_ids.add(slide.slide_id)
        slides.append(slide)
    if not slides:
        raise ValueError(f"no slides found in {path}")
    return slides


def _yaml_str_representer(dumper, data):
    """Use literal block style for multiline strings (cleaner output)."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _PrettyDumper(yaml.SafeDumper):
    pass


_PrettyDumper.add_representer(str, _yaml_str_representer)


def slides_to_yaml_text(slides: list[Slide]) -> str:
    """Serialize a list of slides back to a slides.yaml document.

    Round-trips the original ``raw`` mapping captured at parse time so
    field order and any author-specific keys (within the schema) survive
    migration. Multiline strings are written as literal block scalars
    (``|``) for readability.
    """
    out = [dict(s.raw) for s in slides]
    return yaml.dump(
        out,
        Dumper=_PrettyDumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
