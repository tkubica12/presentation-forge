"""Per-slide content hashing + build-state cache."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .slides_parser import Slide

STATE_VERSION = 1


def hash_slide(slide: Slide) -> str:
    """Hash the normalized slide content (whitespace-trimmed)."""
    parts = [
        slide.slide_id,
        slide.layout.value,
        (slide.title or "").strip(),
        (slide.subtitle or "").strip(),
        "|".join((b or "").strip() for b in slide.bullets),
        (slide.body or "").strip(),
        (slide.image_ref or "").strip(),
        (slide.image_position or "").strip(),
        (slide.notes or "").strip(),
    ]
    return "sha256:" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class State:
    version: int = STATE_VERSION
    slides: dict[str, dict[str, Any]] = field(default_factory=dict)
    images: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "State":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            version=int(raw.get("version", STATE_VERSION)),
            slides=dict(raw.get("slides") or {}),
            images=dict(raw.get("images") or {}),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"version": self.version, "slides": self.slides, "images": self.images},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def record_slide(self, slide_id: str, content_hash: str, *, kind: str) -> None:
        entry = self.slides.setdefault(slide_id, {})
        entry["content_hash"] = content_hash
        entry[f"last_built_{kind}"] = _dt.datetime.now(_dt.UTC).isoformat()

    def slide_changed(self, slide_id: str, current_hash: str) -> bool:
        prev = self.slides.get(slide_id, {}).get("content_hash")
        return prev != current_hash
