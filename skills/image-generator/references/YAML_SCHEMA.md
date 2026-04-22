# YAML schema reference

Detailed reference for the YAML brief consumed by `generate-images`. The short
version lives in [`../SKILL.md`](../SKILL.md).

## Top-level fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `common_requirements` | string (multi-line) | **required** | Baked into every prompt. Brand, mandatory subject, mood, do-not rules. |
| `images` | list | **required**, >= 1 | Each entry is one subject. |
| `variations_description` | string | none | Axes along which variations should differ. Omit to use sensible defaults. |
| `variations_count` | int | `8` | Distinct prompt variants per image. |
| `instances_per_prompt` | int | `1` | Renders per prompt (different random seed). |
| `input_image` | path | none | Optional global reference image for the whole job. |
| `size` | `WxH` string or `auto` | `2048x2048` | Default output size. For slide work prefer `3840x2160`; for square assets use `2048x2048`. |
| `quality` | enum | `high` | GPT Image quality tier: `low`, `medium`, `high`, `auto`. |
| `output_dir` | path | `./output` | Relative to the caller's CWD unless overridden by CLI. |
| `parallelism` | int | `24` | Global concurrent in-flight requests. |
| `parallelism_per_model` | int | `12` | Per-backend concurrency cap. Lower if you keep hitting 429s. |
| `models` | list of strings | `[gpt-image-2]` | Deployment names. Legacy MAI / GPT-image-1.x remain opt-in only. |
| `prompt_model` | string | `gpt-5.4` | Chat deployment used to compile prompt variations. Must exist in your Foundry resource. |
| `style_hint` | string | photoreal preamble | Override only for non-photoreal output (illustration / 3D render). |

## Image entry

```yaml
images:
  - name: signature-mug
    description: |
      A matte-black ceramic mug on a cafe table in warm morning light.
    size: "3840x2160"          # optional per-image override
    input_image: ./logo.jpg    # optional per-image reference image
```

### Image entry fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | **required** | Used in filenames; kebab-case slug recommended. |
| `description` | string | **required** | 1–4 sentence subject description. |
| `size` | `WxH` string or `auto` | inherits top-level `size` | Use per-image when one image needs a different aspect ratio. |
| `input_image` | path | inherits top-level `input_image` | Preferred for logos, product marks, packaging, or other reference-only images. Relative paths resolve from the YAML file's folder. |

## Size rules

### GPT Image 2

- Custom dimensions are supported.
- Each dimension is normalized to a **multiple of 16**.
- Total pixels are normalized into the supported pixel budget:
  - **minimum** `655,360`
  - **maximum** `8,294,400` (exactly `3840x2160`)
- Valid examples:
  - `2048x2048`
  - `3840x2160`
  - `2048x1152`
  - `3072x1728`

### Legacy GPT-image-1.x

Legacy GPT-image-1.x deployments keep the old fixed-size behavior:

- `1024x1024`
- `1536x1024`
- `1024x1536`

If you pass another size with a legacy deployment, the skill snaps it to the
nearest compatible legacy size.

### MAI-Image-2

MAI remains text-to-image only and uses its older width/height constraints.
If an input image is present, MAI tasks are skipped.

## Behavioural rules

- Total renders per run:
  `len(images) × variations_count × instances_per_prompt × len(models)`.
- Cached prompts live at `<output_dir>/<image-slug>/prompts.json` and are
  reused across runs. Delete to recompile.
- Existing PNGs at the target path are **skipped** — reruns are idempotent and
  resume after interruption.
- `images[].input_image` overrides top-level `input_image`.

## Output layout

```
<output_dir>/
  <image-slug>/
    prompts.json
    gpt-image-2/
      <image-slug>_v00_i00.png
      ...
    mai-image-2/
      ...
```

## CLI flags (override YAML)

| Flag | Effect |
|---|---|
| `--output-dir DIR` | Override `output_dir`. |
| `--parallelism N` | Override global concurrency. |
| `--parallelism-per-model N` | Override per-model concurrency. |
| `--only ref1,ref2` | Restrict generation to selected image names. |
| `--dry-run` | Print the planned job (no API calls). |
| `-v` / `--verbose` | Debug logging. |

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `401` / `403` | Caller lacks **Cognitive Services User** role | Fix RBAC; re-run `az login`. |
| `404` | Wrong deployment name | Verify the deployment name in Foundry. |
| `429` retried, eventually succeeds | Quota tight; script honors `Retry-After` | Lower `parallelism_per_model`. |
| `429` failed after retries | Sustained throttle | Drop concurrency; request quota increase. |
| `400 content_policy_violation` | Prompt or output blocked by safety filter | Soften the prompt or change the scene. |
| `400` mentioning width / height | Invalid or unsupported `size` | Use `2048x2048`, `3840x2160`, or another GPT Image 2-compatible size. |
| `input_image not found` | Bad relative path | Make the path relative to the YAML file or use an absolute path. |
