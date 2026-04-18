# presentation-forge

Opinionated agent-driven framework for building presentations from text.
Story and structured slide specs are the **source of truth**; the PPTX is
just a build artifact regenerated from those specs each time.

This repo ships two `agentskills.io`-compatible skills:

| Skill | Purpose |
|-------|---------|
| [`image-generator`](./skills/image-generator) | Generate series of images (with variations + instances) from a YAML brief, using Azure AI Foundry models (MAI-Image-2 + gpt-image-1.5) with Entra auth and parallelism / retry built in. |
| [`presentation-forge`](./skills/presentation-forge) | Author and build presentations from `story.md` + `slides.md` + `images.yaml` + `theme.yaml`. Renders draft + final `.pptx` in-house using `python-pptx`. Calls into the sibling `image-generator` skill for visuals. |

## Why "forge"?

Presentations should be authored as text and *forged* into a deck. Edit
the spec, rebuild — selections of preferred image variants persist
across rebuilds via a sidecar `selections.json`. Hand edits to the
`.pptx` are intentionally lost on rebuild — the contract is that the
spec wins.

## Installing the skills

Using the GitHub CLI (preview):

    gh skill install tkubica12/presentation-forge image-generator
    gh skill install tkubica12/presentation-forge presentation-forge

Or clone and run from this checkout — each skill is a standalone uv
project under `skills/<skill>/`. See each skill's `SKILL.md` for usage.

## Local development

Each skill is independent:

    cd skills/image-generator   && uv sync
    cd skills/presentation-forge && uv sync

Run a smoke test of the presentation-forge example talk (no Azure
required when `--skip-images` is passed):

    cd skills/presentation-forge
    uv run forge validate ./assets/examples/example-talk
    uv run forge build    ./assets/examples/example-talk --skip-images

For full image generation, set up `.env` per `skills/image-generator/SKILL.md`
and drop `--skip-images`.

## License

MIT — see [`LICENSE`](./LICENSE).

The `image-generator` skill ships with its own license noted in its
`SKILL.md` frontmatter; both are MIT-compatible.

> Note: this repo does **not** vendor Anthropic's `pptx` skill. That
> skill's license forbids redistribution outside Anthropic's services, so
> `presentation-forge` builds slides directly with `python-pptx`
> (BSD-3-Clause) and a small in-house renderer.
