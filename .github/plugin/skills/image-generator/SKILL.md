---
name: image-generator
description: |
  Generate batches of photorealistic image variations through Microsoft Foundry by driving MAI-Image-2 and gpt-image-1.5 in parallel from a single declarative YAML brief. Use this skill when the user wants multiple variations of the same subject (different lighting, angle, setting, mood, props), side-by-side comparison between MAI-Image-2 and gpt-image-1.5, hero shots / marketing variants / mood boards, or optional image-to-image variations from a reference picture (gpt-image-1.5 only). Triggers include "make hero shots of...", "generate product photos with variations", "create N stylistic variations", "render mockups with different lighting/angles/scenes". Do NOT use for single ad-hoc generations, video, 3D, vector, or text-in-image rendering.
license: MIT
compatibility: |
  Requires Python 3.12+, the uv package manager, and an Azure AI Foundry resource with the deployments MAI-Image-2, gpt-image-1.5, and a chat deployment (default gpt-5.4). Authentication is Microsoft Entra ID only via DefaultAzureCredential — `az login` locally or a Managed Identity in Azure with the Cognitive Services User role on the Foundry resource. Network egress to *.services.ai.azure.com required. Set AZURE_FOUNDRY_ENDPOINT in the environment (or in a `.env` file in the user's CWD).
metadata:
  repo: tkubica12/image-generator-skill
---

# image-generator

Drive Microsoft Foundry to produce **batches of photorealistic image
variations**, running **MAI-Image-2** and **gpt-image-1.5** in parallel
against the same prompts compiled from one YAML brief.

## When to invoke

Invoke when the user wants:

- A *set* of images (hero shots, marketing variants, mood boards, ...).
- Multiple **variations** of the same subject (different lighting, angle,
  setting, style) so they can pick the best.
- Side-by-side comparison between MAI and gpt-image on the same brief.
- Optional image-to-image variations from a reference picture (gpt-image-1.5
  only; MAI is text-to-image).

Do **not** invoke for single ad-hoc generations the user already has a fully
formed prompt for, or for non-image tasks (video, 3D, vector, text-in-image).

## What the skill produces

For each image entry in the YAML, the script generates
`variations_count × instances_per_prompt × len(models)` PNGs (default
`4 × 2 × 2 = 16`) under
`<output_dir>/<image-slug>/<model-slug>/<image-slug>_v<NN>_i<NN>.png` plus a
`prompts.json` cache.

## Workflow

### 1. Author a YAML brief

Required fields:

- `common_requirements` — directives every image must respect (brand,
  mandatory subject, mood, "do not" rules). Be concrete; treat it as the
  shared system prompt.
- `images` — list of `{name: <kebab-case>, description: <1-4 sentences>}`.

Common optional knobs (defaults shown):

- `variations_description` — axis along which variations should differ. Omit
  to use sensible defaults (lighting/angle/lens/mood/props).
- `variations_count: 4`, `instances_per_prompt: 2`.
- `size: 1024x1024`, `quality: high` (gpt-image-1.5 only).
- `parallelism: 24`, `parallelism_per_model: 12`.
- `models: [MAI-Image-2, gpt-image-1.5]` — drop one to disable that backend.
- `input_image: path` — reference for gpt-image-1.5 image-to-image; MAI tasks
  are skipped automatically when set.
- `prompt_model: gpt-5.4` — chat deployment used to compile prompt variants.

Full reference: [`references/YAML_SCHEMA.md`](references/YAML_SCHEMA.md).
A worked example: [`assets/examples/aurora-coffee.yaml`](assets/examples/aurora-coffee.yaml).

Skeleton:

```yaml
common_requirements: |
  <brand / subject / mood / mandatory and forbidden elements>

variations_description: |
  <axes of variation; OMIT if defaults are fine>

variations_count: 4
instances_per_prompt: 2
size: 1024x1024
quality: high
parallelism: 24
parallelism_per_model: 12

models:
  - MAI-Image-2
  - gpt-image-1.5

images:
  - name: <slug>
    description: |
      <what this specific shot depicts>
```

Authoring rules of thumb:

1. Keep `common_requirements` opinionated — vague briefs produce vague
   variations.
2. Each `images` entry is a distinct *subject*; variations cover stylistic
   differences within a subject.
3. Default to photorealistic; override `style_hint` only if the user
   explicitly wants illustration / 3D render / etc.
4. Confirm with the user before generating > ~30 images
   (`images × variations_count × instances_per_prompt × len(models)`).

### 2. Verify environment

Before invoking the CLI:

- The user must be authenticated to Azure (`az login` locally, or Managed
  Identity in the cloud) with **Cognitive Services User** on the Foundry
  resource. **Authentication is always Microsoft Entra ID — no API keys.**
- `AZURE_FOUNDRY_ENDPOINT` must be set. Either export it, or create a `.env`
  in the user's project CWD using [`assets/env.example`](assets/env.example)
  as the template. Do **not** create a `.env` inside the skill directory —
  it is shared across runs and would not be portable.
- Deployments named `MAI-Image-2`, `gpt-image-1.5`, and the chosen
  `prompt_model` must exist on that resource.
- One-time bootstrap: `uv --directory <skill-dir> sync`.

### 3. Run the CLI

From the **user's project directory**. Note that `uv --directory` changes
the working directory to the skill folder, so always pass **absolute paths**
for the YAML file and **always set `--output-dir`** to a path under the
user's project (otherwise outputs land inside the skill folder):

```powershell
uv --directory <skill-dir> run generate-images `
    (Resolve-Path <path-to-yaml>) --output-dir "$PWD\output"
# Useful flags:
#   --dry-run                       print the plan; no API calls
#   --output-dir DIR                override YAML 'output_dir'
#   --parallelism N                 override global concurrency
#   --parallelism-per-model N       override per-backend cap
#   -v / --verbose                  debug logging
```

`<skill-dir>` is wherever `gh skill install` placed this skill — typically
`.agents/skills/image-generator` (project scope) or
`~/.copilot/skills/image-generator` (user scope).

The CLI prints a JSON summary at the end:

```json
{
  "total": 32,
  "generated": 32,
  "skipped_existing": 0,
  "skipped_other": 0,
  "failed": 0,
  "output_dir": "...",
  "failures": []
}
```

### 4. Iterate

- Re-running is **idempotent**: cached prompts in `<output>/<image>/prompts.json`
  and existing PNGs are reused. Delete files to selectively regenerate.
- To recompile prompts only: delete `<output>/<image>/prompts.json`.
- To explore a different axis: edit `variations_description` AND delete the
  cached `prompts.json`.
- To raise variation count after the fact: bump `variations_count` and rerun;
  existing PNGs are kept, only the new variants are generated.

## Failure modes — quick reference

- `401`/`403` → caller missing **Cognitive Services User**; fix RBAC or
  re-`az login` with the right account.
- `404` → deployment name typo. Confirm with
  `az cognitiveservices account deployment list ...`.
- `429` → script honors `Retry-After` and backs off; if it still fails,
  lower `parallelism_per_model` and rerun (idempotent).
- `400 content_policy_violation` (gpt-image-1.5) → soften the prompt or drop
  `gpt-image-1.5` from `models`; MAI may still complete.

Full table in [`references/YAML_SCHEMA.md`](references/YAML_SCHEMA.md#failure-modes).

## Don'ts

- No API keys anywhere — Entra ID only.
- Don't bundle `.env` inside the skill directory; create it in the user's
  project CWD.
- Don't request more than ~50 images in a single run without confirming
  cost/quota with the user.
