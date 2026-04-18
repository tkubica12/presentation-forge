"""YAML configuration loader and schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_VARIATIONS = 4
DEFAULT_INSTANCES = 2
DEFAULT_PARALLELISM = 24
DEFAULT_PARALLELISM_PER_MODEL = 12
DEFAULT_OUTPUT_DIR = "./output"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "high"
DEFAULT_MODELS = ["MAI-Image-2", "gpt-image-1.5"]
DEFAULT_PROMPT_MODEL = "gpt-5.4"


@dataclass
class ImageSpec:
    name: str
    description: str


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
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping in {path}")
        images_raw = data.get("images") or []
        if not images_raw:
            raise ValueError("YAML must contain non-empty 'images' list")
        images = [ImageSpec(name=str(i["name"]), description=str(i["description"])) for i in images_raw]

        kwargs = {k: v for k, v in data.items() if k != "images"}
        kwargs["images"] = images
        # Drop unknown keys gracefully
        allowed = set(JobConfig.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in kwargs.items() if k in allowed}
        return JobConfig(**kwargs)
