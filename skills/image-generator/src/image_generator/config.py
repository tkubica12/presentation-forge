"""YAML configuration loader and schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_VARIATIONS = 8
DEFAULT_INSTANCES = 1
DEFAULT_PARALLELISM = 24
DEFAULT_PARALLELISM_PER_MODEL = 12
DEFAULT_OUTPUT_DIR = "./output"
DEFAULT_SIZE = "2048x2048"
DEFAULT_QUALITY = "high"
DEFAULT_MODELS = ["gpt-image-2"]
DEFAULT_PROMPT_MODEL = "gpt-5.4"


@dataclass
class ImageSpec:
    name: str
    description: str
    size: Optional[str] = None  # per-image size override (e.g., "1536x1024")
    input_image: Optional[str] = None  # optional per-image reference image


@dataclass
class JobConfig:
    common_requirements: str
    images: list[ImageSpec]
    variations_description: Optional[str] = None
    variations_count: int = DEFAULT_VARIATIONS
    instances_per_prompt: int = DEFAULT_INSTANCES
    input_image: Optional[str] = None
    output_dir: str = DEFAULT_OUTPUT_DIR
    parallelism: int = DEFAULT_PARALLELISM
    parallelism_per_model: int = DEFAULT_PARALLELISM_PER_MODEL
    size: str = DEFAULT_SIZE
    quality: str = DEFAULT_QUALITY
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    prompt_model: str = DEFAULT_PROMPT_MODEL
    style_hint: str = (
        "Photorealistic, ultra high resolution, professionally lit, sharp focus, "
        "natural depth of field, color-accurate."
    )

    @staticmethod
    def from_yaml(path: str | Path) -> "JobConfig":
        path = Path(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping in {path}")
        base_dir = path.resolve().parent
        images_raw = data.get("images") or []
        if not images_raw:
            raise ValueError("YAML must contain non-empty 'images' list")
        images = [
            ImageSpec(
                name=str(i["name"]),
                description=str(i["description"]),
                size=i.get("size"),
                input_image=_resolve_optional_path(i.get("input_image"), base_dir),
            )
            for i in images_raw
        ]

        kwargs = {k: v for k, v in data.items() if k != "images"}
        kwargs["images"] = images
        # Drop unknown keys gracefully
        allowed = set(JobConfig.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in kwargs.items() if k in allowed}
        if "input_image" in kwargs:
            kwargs["input_image"] = _resolve_optional_path(kwargs["input_image"], base_dir)
        return JobConfig(**kwargs)


def _resolve_optional_path(value: object, base_dir: Path) -> Optional[str]:
    if value in (None, ""):
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)
