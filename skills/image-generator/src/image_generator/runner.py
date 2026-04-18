"""Async orchestrator: compile prompts, fan out generation across models."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from .auth import TokenCache
from .backends import (
    GenerationError,
    generate_gpt_image,
    generate_mai_image,
    prepare_input_image,
)
from .config import JobConfig
from .prompts import generate_variations

log = logging.getLogger(__name__)


def _slug(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return s or "image"


@dataclass
class Task:
    image_name: str
    model: str
    variation_index: int
    instance_index: int
    prompt: str
    output_path: Path


def _output_path(
    base: Path, image_name: str, model: str, var: int, inst: int
) -> Path:
    return (
        base
        / _slug(image_name)
        / _slug(model)
        / f"{_slug(image_name)}_v{var:02d}_i{inst:02d}.png"
    )


def _prompts_path(base: Path, image_name: str) -> Path:
    return base / _slug(image_name) / "prompts.json"


async def _build_or_load_prompts(
    *,
    cfg: JobConfig,
    endpoint: str,
    token_cache: TokenCache,
    client: httpx.AsyncClient,
    out_dir: Path,
) -> dict[str, list[str]]:
    """Return {image_name: [variation_prompt, ...]} reusing cached prompts.json."""
    result: dict[str, list[str]] = {}

    async def _one(image) -> tuple[str, list[str]]:
        cache = _prompts_path(out_dir, image.name)
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                cached = data.get("variations") or []
                if len(cached) >= cfg.variations_count:
                    log.info("Reusing cached prompts for %s", image.name)
                    return image.name, cached[: cfg.variations_count]
            except Exception:  # noqa: BLE001
                log.warning("Bad cache at %s, regenerating", cache)
        prompts = await generate_variations(
            endpoint=endpoint,
            deployment=cfg.prompt_model,
            token_cache=token_cache,
            common_requirements=cfg.common_requirements,
            style_hint=cfg.style_hint,
            image_name=image.name,
            image_description=image.description,
            variation_guidance=cfg.variations_description,
            count=cfg.variations_count,
            client=client,
        )
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "image": {"name": image.name, "description": image.description},
                    "variations": prompts,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return image.name, prompts

    coros = [_one(img) for img in cfg.images]
    for name, prompts in await asyncio.gather(*coros):
        result[name] = prompts
    return result


def _build_tasks(
    cfg: JobConfig, prompts: dict[str, list[str]], out_dir: Path
) -> list[Task]:
    tasks: list[Task] = []
    for image in cfg.images:
        for v_idx, p in enumerate(prompts[image.name]):
            for i_idx in range(cfg.instances_per_prompt):
                for model in cfg.models:
                    tasks.append(
                        Task(
                            image_name=image.name,
                            model=model,
                            variation_index=v_idx,
                            instance_index=i_idx,
                            prompt=p,
                            output_path=_output_path(
                                out_dir, image.name, model, v_idx, i_idx
                            ),
                        )
                    )
    return tasks


async def _run_task(
    task: Task,
    *,
    cfg: JobConfig,
    endpoint: str,
    token_cache: TokenCache,
    input_image_prepared: Optional[Path],
    client: httpx.AsyncClient,
    global_sem: asyncio.Semaphore,
    model_sems: dict[str, asyncio.Semaphore],
) -> tuple[Task, bool, Optional[str]]:
    if task.output_path.exists() and task.output_path.stat().st_size > 0:
        return task, True, "exists"
    task.output_path.parent.mkdir(parents=True, exist_ok=True)
    model_sem = model_sems[task.model]
    # Per-model first (the scarce resource), then global. Keeps fair use across
    # models and prevents one slow backend from monopolising the global pool.
    async with model_sem, global_sem:
        try:
            if task.model.lower().startswith("mai"):
                if input_image_prepared is not None:
                    log.info(
                        "Skipping %s — MAI does not accept input images",
                        task.output_path,
                    )
                    return task, False, "mai-no-input-image"
                png = await generate_mai_image(
                    endpoint=endpoint,
                    deployment=task.model,
                    token_cache=token_cache,
                    prompt=task.prompt,
                    size=cfg.size,
                    client=client,
                )
            else:
                png = await generate_gpt_image(
                    endpoint=endpoint,
                    deployment=task.model,
                    token_cache=token_cache,
                    prompt=task.prompt,
                    size=cfg.size,
                    quality=cfg.quality,
                    input_image_path=input_image_prepared,
                    client=client,
                )
            task.output_path.write_bytes(png)
            return task, True, "generated"
        except GenerationError as exc:
            log.error("FAIL %s: %s", task.output_path, exc)
            return task, False, str(exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected failure for %s", task.output_path)
            return task, False, f"{type(exc).__name__}: {exc}"


async def run_job(cfg: JobConfig, *, endpoint: str) -> dict:
    out_dir = Path(cfg.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    input_image_prepared: Optional[Path] = None
    if cfg.input_image:
        src = Path(cfg.input_image)
        if not src.exists():
            raise FileNotFoundError(f"input_image not found: {src}")
        input_image_prepared = prepare_input_image(
            src, dst=out_dir / ".cache" / f"{_slug(src.stem)}.png"
        )

    token_cache = TokenCache()
    timeout = httpx.Timeout(300.0, connect=30.0)
    max_conn = max(cfg.parallelism, cfg.parallelism_per_model * len(cfg.models)) * 2
    limits = httpx.Limits(max_connections=max_conn, max_keepalive_connections=max_conn)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        prompts = await _build_or_load_prompts(
            cfg=cfg,
            endpoint=endpoint,
            token_cache=token_cache,
            client=client,
            out_dir=out_dir,
        )
        tasks = _build_tasks(cfg, prompts, out_dir)
        per_model = max(1, cfg.parallelism_per_model)
        log.info(
            "Planning %d images (%d images × %d variations × %d instances × %d models); "
            "global parallelism=%d, per-model=%d",
            len(tasks),
            len(cfg.images),
            cfg.variations_count,
            cfg.instances_per_prompt,
            len(cfg.models),
            cfg.parallelism,
            per_model,
        )
        global_sem = asyncio.Semaphore(cfg.parallelism)
        model_sems = {m: asyncio.Semaphore(per_model) for m in cfg.models}
        results = await asyncio.gather(
            *[
                _run_task(
                    t,
                    cfg=cfg,
                    endpoint=endpoint,
                    token_cache=token_cache,
                    input_image_prepared=input_image_prepared,
                    client=client,
                    global_sem=global_sem,
                    model_sems=model_sems,
                )
                for t in tasks
            ]
        )

    summary = {
        "total": len(results),
        "generated": sum(1 for _, ok, why in results if ok and why == "generated"),
        "skipped_existing": sum(1 for _, ok, why in results if ok and why == "exists"),
        "skipped_other": sum(
            1 for _, ok, why in results if ok and why not in ("exists", "generated")
        ),
        "failed": sum(1 for _, ok, _ in results if not ok),
        "output_dir": str(out_dir),
        "failures": [
            {"path": str(t.output_path), "reason": why}
            for t, ok, why in results
            if not ok
        ],
    }
    return summary
