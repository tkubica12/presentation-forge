---
name: image-generator
description: |
  Generate batches of photorealistic image variations through Microsoft Foundry, using GPT Image 2 by default and optionally legacy MAI-Image-2 / GPT-image-1.x deployments when explicitly requested. Use this skill when the user wants multiple variations of the same subject, higher-resolution slide-ready imagery, or image-to-image work from a reference picture such as a logo or product mark. Do NOT use for single ad-hoc generations, video, 3D, vector, or text-in-image rendering.
license: MIT
compatibility: |
  Requires Python 3.12+, the uv package manager, and an Azure AI Foundry resource with a GPT Image 2 deployment plus a chat deployment (default gpt-5.4). Legacy MAI-Image-2 / GPT-image-1.x deployments are optional. Authentication is Microsoft Entra ID only via DefaultAzureCredential — `az login` locally or a Managed Identity in Azure with the Cognitive Services User role on the Foundry resource. Network egress to *.services.ai.azure.com required. Set AZURE_FOUNDRY_ENDPOINT in the environment (or in a `.env` file in the user's CWD).
metadata:
  repo: tkubica12/image-generator-skill
---

# image-generator

Drive Microsoft Foundry to produce **batches of photorealistic image
variations** from one YAML brief. The default backend is **GPT Image 2**:
custom dimensions, input-image edits, and higher-resolution output. Legacy
MAI / GPT-image-1.x are still supported if the user explicitly asks for them.

## When to invoke

Invoke when the user wants:

- A *set* of images (hero shots, marketing variants, mood boards, ...).
- Multiple **variations** of the same subject so they can pick the best.
- **Slide-ready output sizes** — especially exact `16:9` imagery.
- **Image-to-image** work from a reference picture (logo, product shot,
  packaging mark, style anchor).

Do **not** invoke for single ad-hoc generations the user already has a fully
formed prompt for, or for non-image tasks (video, 3D, vector, text-in-image).

## What the skill produces

For each image entry in the YAML, the script generates
`variations_count × instances_per_prompt × len(models)` PNGs (default
`8 × 1 × 1 = 8`) under
`<output_dir>/<image-slug>/<model-slug>/<image-slug>_v<NN>_i<NN>.png` plus a
`prompts.json` cache.

## Workflow

### 1. Author a YAML brief

Required fields:

- `common_requirements` — directives every image must respect (brand,
  mandatory subject, mood, "do not" rules). Be concrete; treat it as the
  shared system prompt.
- `images` — list of `{name, description}` entries. Each entry is one
  subject; variations explore different takes of that subject.

Common optional knobs (defaults shown):

- `variations_description` — axis along which variations should differ. Omit
  to use sensible defaults (lighting / angle / lens / mood / props).
- `variations_count: 8`, `instances_per_prompt: 1`.
- `size: 2048x2048`, `quality: high`.
- `parallelism: 24`, `parallelism_per_model: 12`.
- `models: [gpt-image-2]`.
- `input_image: path` — optional top-level reference image for the whole job.
- `images[].input_image: path` — optional per-image reference image (preferred
  when only some images use a logo / reference).
- `prompt_model: gpt-5.4` — chat deployment used to compile prompt variations.

**Size guidance**

- **Square / 1:1** → use `2048x2048`.
- **Slide / 16:9** → use `3840x2160`.
- GPT Image 2 accepts custom dimensions; the skill normalizes them to the
  model's rules (multiple of 16, within the pixel budget).
- Legacy GPT-image-1.x deployments still snap to the old fixed sizes
  (`1024x1024`, `1536x1024`, `1024x1536`).

Full reference: [`references/YAML_SCHEMA.md`](references/YAML_SCHEMA.md).
A worked example: [`assets/examples/aurora-coffee.yaml`](assets/examples/aurora-coffee.yaml).

Skeleton:

```yaml
common_requirements: |
  <brand / subject / mood / mandatory and forbidden elements>

variations_description: |
  <axes of variation; omit if defaults are fine>

variations_count: 8
instances_per_prompt: 1
size: 2048x2048
quality: high
parallelism: 24
parallelism_per_model: 12

models:
  - gpt-image-2

images:
  - name: <slug>
    description: |
      <what this specific shot depicts>
    # Optional when this image needs a logo / reference picture:
    # input_image: ./my-logo.jpg
```

Authoring rules of thumb:

1. Keep `common_requirements` opinionated — vague briefs produce vague
   variations.
2. Use **per-image `input_image`** for logos / marks / product labels so only
   the relevant images inherit that reference.
3. For presentation work, default to **`3840x2160`** unless the image is
   intentionally square.
4. Confirm with the user before generating > ~30 images
   (`images × variations_count × instances_per_prompt × len(models)`).

### 2. Verify environment

Before invoking the CLI:

- The user must be authenticated to Azure (`az login` locally, or Managed
  Identity in the cloud) with **Cognitive Services User** on the Foundry
  resource. **Authentication is always Microsoft Entra ID — no API keys.**
- `AZURE_FOUNDRY_ENDPOINT` must be set. Either export it, or create a `.env`
  in the user's project CWD using [`assets/env.example`](assets/env.example)
  as the template. Do **not** create a `.env` inside the skill directory — it
  is shared across runs and would not be portable.
- A deployment named `gpt-image-2` (or whatever name the YAML uses in
  `models`) plus the chosen `prompt_model` must exist on that resource.
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
#   --only ref1,ref2                restrict to selected image names
#   -v / --verbose                  debug logging
```

The CLI prints per-task progress lines as it runs:

```text
[  3/  8] signature-mug gpt-image-2 v02 i00 → generated
```

…and a JSON summary at the end:

```json
{
  "total": 8,
  "generated": 8,
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
- To explore a different axis: edit `variations_description` and delete the
  cached `prompts.json`.
- To raise variation count after the fact: bump `variations_count` and rerun;
  existing PNGs are kept, only the new variants are generated.

## Failure modes — quick reference

- `401` / `403` → caller missing **Cognitive Services User**; fix RBAC or
  re-`az login` with the right account.
- `404` → deployment name typo. Confirm the actual deployment names in Foundry.
- `429` → script honors `Retry-After` and backs off; if it still fails, lower
  `parallelism_per_model` and rerun (idempotent).
- `400 content_policy_violation` → soften the prompt or try a different image.
- `400` mentioning width / height → invalid or unsupported `size`; use
  `2048x2048`, `3840x2160`, or another GPT Image 2-compatible size.

Full table in [`references/YAML_SCHEMA.md`](references/YAML_SCHEMA.md#failure-modes).

## Don'ts

- No API keys anywhere — Entra ID only.
- Don't bundle `.env` inside the skill directory; create it in the user's
  project CWD.
- Don't request more than ~50 images in a single run without confirming
  cost / quota with the user.
