"""Shared pytest fixtures for presentation-forge tests."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_POTX = REPO_ROOT / ".templates" / "Microsoft-Azure-PowerPoint-Template-2604.potx"


def _png_bytes(color: tuple[int, int, int] = (200, 100, 50)) -> bytes:
    """Build a minimal valid 2x2 PNG (no Pillow dep needed)."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(color) * 2 for _ in range(2))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture
def png_bytes():
    """Factory for tiny valid PNG bytes with a chosen RGB tint."""
    return _png_bytes


def _write_minimal_presentation_files(folder: Path, *, with_template: bool) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.md").write_text("# story\n", encoding="utf-8")
    (folder / "slides.md").write_text(
        dedent(
            """\
            ---
            slide-id: title
            layout: title
            title: "Hello"
            subtitle: "World"
            notes: |
              Welcome speaker notes.
            ---

            ---
            slide-id: hero
            layout: full-bleed-image
            title: "Big picture"
            image_ref: hero-img
            ---

            ---
            slide-id: points
            layout: bullets
            title: "Three things"
            bullets:
              - first thing
              - second thing
              - third thing
            ---

            ---
            slide-id: side
            layout: bullets-with-image
            title: "Side by side"
            bullets:
              - left point
              - another point
            image_ref: side-img
            image_position: right
            ---

            ---
            slide-id: q
            layout: quote
            body: "Be the change."
            subtitle: "Gandhi"
            ---

            ---
            slide-id: single
            layout: image-single
            title: "Solo shot"
            image_ref: hero-img
            ---

            ---
            slide-id: duo
            layout: image-duo
            title: "Two views"
            image_ref: side-img
            ---

            ---
            slide-id: end
            layout: section-divider
            title: "Thanks"
            subtitle: "questions?"
            ---
            """
        ),
        encoding="utf-8",
    )
    (folder / "images.yaml").write_text(
        dedent(
            """\
            images:
              - name: hero-img
                description: hero image
              - name: side-img
                description: side image
            """
        ),
        encoding="utf-8",
    )
    theme: dict = {
        "fonts": {"heading": "Arial", "body": "Arial"},
        "colors": {"accent": "#0078D4"},
    }
    if with_template:
        rel = (
            TEMPLATE_POTX.resolve()
            .relative_to(folder.resolve(), walk_up=True)
            if hasattr(Path, "walk_up") or False
            else None
        )
        # Use absolute path – simpler & robust regardless of tmp layout.
        theme["template"] = str(TEMPLATE_POTX.resolve())
        theme["layouts"] = {
            "title": "Title Slide 1",
            "section-divider": "Section Slide 1",
            "bullets": "Title and Content",
            "bullets-with-image": "Photo Slide 1",
            "full-bleed-image": "Photo full bleed lower title",
            "two-column": "Two Column Bullet text",
            "quote": "Quote",
            "comparison": "Two Column Bullet text",
            "image-grid": "Three Filmstrip Photos",
            "image-single": "Title Only",
            "image-duo": "Two picture content",
            "appendix-references": "Title & Non-bulleted text",
        }
        theme["metadata"] = {"author": "tests", "subject": "test deck"}
    import yaml

    (folder / "theme.yaml").write_text(yaml.safe_dump(theme), encoding="utf-8")


@pytest.fixture
def make_presentation_dir(tmp_path):
    """Build a self-contained example presentation folder under tmp_path."""

    def _make(name: str = "deck", *, with_template: bool = False) -> Path:
        folder = tmp_path / name
        _write_minimal_presentation_files(folder, with_template=with_template)
        return folder

    return _make


@pytest.fixture
def populate_image_variants():
    """Drop tiny PNG variants under ``<folder>/build/images/<ref>/<model>/``."""

    def _populate(
        folder: Path,
        image_ref: str,
        *,
        models: tuple[str, ...] = ("gpt-image-1",),
        variations: int = 2,
        instances: int = 1,
        color: tuple[int, int, int] = (123, 45, 67),
    ) -> list[Path]:
        out: list[Path] = []
        base = folder / "build" / "images" / image_ref
        for model in models:
            md = base / model
            md.mkdir(parents=True, exist_ok=True)
            for v in range(1, variations + 1):
                for i in range(1, instances + 1):
                    p = md / f"{image_ref}_v{v:02d}_i{i:02d}.png"
                    p.write_bytes(_png_bytes(color))
                    out.append(p)
        return out

    return _populate


@pytest.fixture
def microsoft_template_path() -> Path:
    """Returns the user's MS Azure template path; skip the test if absent."""
    if not TEMPLATE_POTX.exists():
        pytest.skip(f"Microsoft template not present at {TEMPLATE_POTX}")
    return TEMPLATE_POTX
