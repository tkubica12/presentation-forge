# YAML schema reference

Detailed reference for the YAML brief consumed by `generate-images`. The
short version lives in [`SKILL.md`](../SKILL.md); use this file when you need
the full field list, defaults, and edge cases.

## Top-level fields

| Field                    | Type                  | Default              | Notes |
|--------------------------|-----------------------|----------------------|-------|
| `common_requirements`    | string (multi-line)   | **required**         | Baked into every prompt. Brand, mandatory subject, mood, do-not rules. |
| `images`                 | list                  | **required**, ≥ 1    | Each entry: `name` (kebab-case slug), `description` (1-4 sentences). |
| `variations_description` | string                | none                 | Axes along which variations should differ. Omit to use sensible defaults. |
| `variations_count`       | int                   | `4`                  | Distinct prompt variants per image. |
| `instances_per_prompt`   | int                   | `2`                  | Renders per prompt (different random seed). |
| `input_image`            | path                  | none                 | Reference image for image-to-image. Forces gpt-image-1.5 only; MAI is skipped. |
| `size`                   | `WxH` string          | `1024x1024`          | Auto-clamped per backend (MAI ≥ 768 each, ≤ 1,048,576 px; gpt-image snaps to 1024×1024 / 1024×1536 / 1536×1024). |
| `quality`                | enum                  | `high`               | gpt-image only: `low`, `medium`, `high`, `auto`. |
| `output_dir`             | path                  | `./output`           | Relative to the user's CWD. |
| `parallelism`            | int                   | `24`                 | Global concurrent in-flight requests. |
| `parallelism_per_model`  | int                   | `12`                 | Per-backend concurrency cap. Lower if you keep hitting 429s. |
| `models`                 | list of strings       | `[MAI-Image-2, gpt-image-1.5]` | Foundry deployment names. Drop one to disable that backend. |
| `prompt_model`           | string                | `gpt-5.4`            | Chat deployment used to compile prompt variations. Must exist in your Foundry resource. |
| `style_hint`             | string                | photoreal preamble   | Override only for non-photoreal output (illustration / 3D render). |

## Image entry

```yaml
images:
  - name: morning-ritual          # used in filenames; kebab-case slug
    description: |                # 1-4 sentence subject description
      The Aurora ceramic mug filled with espresso on an oak countertop next
      to an open notebook and a fountain pen.
```

## Behavioural rules

- Total renders per run: `len(images) × variations_count × instances_per_prompt × len(models)`.
- Cached prompts live at `<output_dir>/<image-slug>/prompts.json` and are
  reused across runs. Delete to recompile.
- Existing PNGs at the target path are **skipped** — reruns are idempotent
  and resume after interruption.
- `MAI-Image-2` is text-to-image only. Specifying `input_image` skips MAI
  tasks for that job.

## Output layout

```
<output_dir>/
  <image-slug>/
    prompts.json
    mai-image-2/
      <image-slug>_v00_i00.png
      <image-slug>_v00_i01.png
      ...
    gpt-image-1.5/
      <image-slug>_v00_i00.png
      ...
```

## CLI flags (override YAML)

| Flag                          | Effect |
|-------------------------------|--------|
| `--output-dir DIR`            | Override `output_dir`. |
| `--parallelism N`             | Override global concurrency. |
| `--parallelism-per-model N`   | Override per-backend cap. |
| `--dry-run`                   | Print the planned job (no API calls). |
| `-v` / `--verbose`            | Debug logging. |

## Failure modes

| Symptom                                   | Likely cause                                   | Action |
|-------------------------------------------|------------------------------------------------|--------|
| `401` / `403`                              | Caller lacks **Cognitive Services User** role  | Fix RBAC; re-run `az login`. |
| `404`                                      | Wrong deployment name                          | `az cognitiveservices account deployment list ...` |
| `429` retried, eventually succeeds         | Quota tight — script honors `Retry-After`      | Lower `parallelism_per_model`. |
| `429` failed after 8 retries               | Sustained throttle                             | Drop concurrency, request quota increase. |
| `400 content_policy_violation`             | gpt-image-1.5 safety filter                    | Soften prompt; or drop `gpt-image-1.5` from `models`. |
| `MAI 400` mentioning width/height          | Invalid `size` string                          | Use `WxH` numeric form. |
