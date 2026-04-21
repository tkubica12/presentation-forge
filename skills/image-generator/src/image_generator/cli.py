"""Command-line entry point."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import JobConfig
from .runner import run_job


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate-images",
        description=(
            "Generate batches of photorealistic image variations against "
            "Microsoft Foundry (MAI-Image-2 + gpt-image-1.5)."
        ),
    )
    parser.add_argument("config", help="Path to a YAML job definition")
    parser.add_argument(
        "--output-dir",
        help="Override output directory (defaults to YAML 'output_dir' or ./output)",
    )
    parser.add_argument(
        "--parallelism", type=int, help="Override global parallel request count"
    )
    parser.add_argument(
        "--parallelism-per-model",
        type=int,
        help="Override per-model parallel request count (cap per backend)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compile prompts only; do not call image generation APIs.",
    )
    parser.add_argument(
        "--only",
        help=(
            "Comma-separated image names; restrict generation to these refs. "
            "Other entries in the YAML are skipped entirely."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    load_dotenv()
    endpoint = os.environ.get("AZURE_FOUNDRY_ENDPOINT") or os.environ.get(
        "AZURE_ENDPOINT"
    )
    if not endpoint:
        sys.stderr.write(
            "ERROR: AZURE_FOUNDRY_ENDPOINT not set. Create a .env file (see "
            ".env.example) or export the variable.\n"
        )
        return 2

    cfg = JobConfig.from_yaml(args.config)
    if args.output_dir:
        cfg.output_dir = args.output_dir
    if args.parallelism:
        cfg.parallelism = args.parallelism
    if args.parallelism_per_model:
        cfg.parallelism_per_model = args.parallelism_per_model
    if args.only:
        wanted = {n.strip() for n in args.only.split(",") if n.strip()}
        known = {img.name for img in cfg.images}
        unknown = wanted - known
        if unknown:
            sys.stderr.write(
                f"ERROR: --only references unknown image(s): {sorted(unknown)}\n"
                f"Known: {sorted(known)}\n"
            )
            return 2
        cfg.images = [img for img in cfg.images if img.name in wanted]
        if not cfg.images:
            sys.stderr.write("ERROR: --only filter matched no images.\n")
            return 2
        print(
            f"--only: limiting to {sorted(wanted)} ({len(cfg.images)} images)",
            file=sys.stderr,
        )

    if args.dry_run:
        # Just print what we would do.
        print(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "models": cfg.models,
                    "images": [i.name for i in cfg.images],
                    "variations_count": cfg.variations_count,
                    "instances_per_prompt": cfg.instances_per_prompt,
                    "parallelism": cfg.parallelism,
                    "parallelism_per_model": cfg.parallelism_per_model,
                    "output_dir": str(Path(cfg.output_dir).resolve()),
                    "would_generate": (
                        len(cfg.images)
                        * cfg.variations_count
                        * cfg.instances_per_prompt
                        * len(cfg.models)
                    ),
                },
                indent=2,
            )
        )
        return 0

    summary = asyncio.run(run_job(cfg, endpoint=endpoint))
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
