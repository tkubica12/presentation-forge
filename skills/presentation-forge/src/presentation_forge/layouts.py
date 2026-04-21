"""Slide layout enum and per-layout placeholder mapping."""
from __future__ import annotations

from enum import Enum


class Layout(str, Enum):
    TITLE = "title"
    COVER = "cover"
    SECTION_DIVIDER = "section-divider"
    BULLETS = "bullets"
    BULLETS_WITH_IMAGE = "bullets-with-image"
    FULL_BLEED_IMAGE = "full-bleed-image"
    TWO_COLUMN = "two-column"
    QUOTE = "quote"
    COMPARISON = "comparison"
    IMAGE_GRID = "image-grid"
    IMAGE_SINGLE = "image-single"
    IMAGE_DUO = "image-duo"
    APPENDIX_REFERENCES = "appendix-references"


REQUIRED_FIELDS: dict[Layout, set[str]] = {
    Layout.TITLE: {"title"},
    Layout.COVER: {"title", "image_ref"},
    Layout.SECTION_DIVIDER: {"title"},
    Layout.BULLETS: {"title", "bullets"},
    Layout.BULLETS_WITH_IMAGE: {"title", "bullets", "image_ref"},
    Layout.FULL_BLEED_IMAGE: {"image_ref"},
    Layout.TWO_COLUMN: {"title", "bullets"},
    Layout.QUOTE: {"body"},
    Layout.COMPARISON: {"title", "bullets"},
    Layout.IMAGE_GRID: {"title"},
    Layout.IMAGE_SINGLE: {"title", "image_ref"},
    Layout.IMAGE_DUO: {"title", "image_ref"},
    Layout.APPENDIX_REFERENCES: {"title", "body"},
}


def needs_image(layout: Layout) -> bool:
    return layout in {
        Layout.COVER,
        Layout.BULLETS_WITH_IMAGE,
        Layout.FULL_BLEED_IMAGE,
        Layout.IMAGE_GRID,
        Layout.IMAGE_SINGLE,
        Layout.IMAGE_DUO,
    }


def can_have_image(layout: Layout) -> bool:
    return needs_image(layout) or layout in {Layout.TITLE}
