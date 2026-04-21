---
name: presentation-forge
description: |
  Opinionated framework for building presentations from a text-first spec where the PPTX is just a build artifact. A presentation lives in a folder containing story.md (free-form narrative), slides.yaml (ordered slides with stable slide-ids), images.yaml (consumed by the image-generator skill), theme.yaml (template + brand tokens), and selections.yaml (per-slide chosen image variant). The `forge` CLI scaffolds this folder, validates it, runs image generation, and renders draft.pptx (every variation as alternate slides) plus final.pptx (one image per slide using selections.yaml). Use this skill whenever the user wants to author or iterate on a presentation, especially when they want AI-generated images integrated into a narrative-first workflow. Triggers: "build a deck", "create a presentation", "draft slides about X", "generate a pitch deck", "iterate on my talk". Do NOT use for one-off slide edits in an existing PPTX the user already owns.
license: MIT
compatibility: |
  Requires Python 3.12+, the uv package manager, and (for image generation) the sibling `image-generator` skill from this repo plus an Azure AI Foundry resource (see image-generator's compatibility). PPTX rendering is in-house using python-pptx (no external skill dependency). Optional: LibreOffice (`soffice`) and Poppler (`pdftoppm`) for slide-thumbnail previews.
metadata:
  repo: tkubica12/presentation-forge
  peer-skills: image-generator
---

# presentation-forge

Build presentations as **text-first specs**. Story, structure, and image
briefs are the source of truth; the PPTX is a build artifact that is
always regenerated from spec.

## When to invoke

Invoke when the user wants to:

- Author a new presentation collaboratively (research → narrative → slide
  outline → image briefs).
- Iterate on an existing presentation in this repo where edits to text/spec
  should re-flow into the PPTX without losing image-variant selections.
- Generate AI images side-by-side with slide content.

Do **not** invoke for one-off edits to a PPTX the user already owns — use
the system PPTX tooling for that.

## Per-presentation folder layout

```
my-talk/
  story.md            # free-form narrative, audience, goals, references
  slides.yaml         # ordered list of slides (stable slide-ids + layout/content)
  images.yaml         # exact format the image-generator skill consumes
  theme.yaml          # template.pptx path + fonts + brand colors + logo
  selections.yaml     # per-slide-id -> chosen image variant (state file)
  build/
    state.json        # internal: per-slide content hash + last-built timestamp
    images/           # output_dir for image-generator (cached, idempotent)
    draft.pptx        # all image variations as alternate slides for review
    final.pptx        # one image per slide based on selections.yaml
```

> **Legacy formats** (`slides.md`, `selections.json`) are still loaded
> when present, so existing folders keep working. Convert any folder
> with `forge migrate <folder>`.

Every artifact except `build/` is meant to be human-edited and committed to
version control.

## Workflow (ideation → build → iterate)

### Phase 1: Ideate

Walk the user through, in this order:

1. **Story.md** — narrative shape. Ask:
   - Who is the audience?
   - What is the central thesis / takeaway in one sentence?
   - What 3-5 supporting beats carry it?
   - What references / sources should the agent ground in (URLs, docs)?

2. **Slides.yaml** — turn the story into an ordered list of slides. For each:
   - Stable `slide-id` (kebab-case, never reuse).
   - One of the supported `layout` values (see
     [`references/SLIDES_FORMAT.md`](references/SLIDES_FORMAT.md)).
   - Title, bullets / body text, optional `image_ref`, speaker notes.
   - Discuss with user; do not invent slides without their input.

3. **Images.yaml** — for any slide that needs an image, draft an entry in
   `images.yaml`. The schema is exactly the image-generator skill's
   ([`../image-generator/references/YAML_SCHEMA.md`](../image-generator/references/YAML_SCHEMA.md)).
   `slides.md` references images by their `images[].name`.

4. **Theme.yaml** — point at a template (one of the shipped starters in
   `assets/templates/` or a user-provided `template.pptx`) plus brand
   tokens.

Use `forge new <dir>` to scaffold all four files from templates. Then
co-author each in turn.

### Phase 2: Build

```powershell
forge validate                  # spec lint
forge images                    # run image-generator (cached / restartable)
forge build                     # produces draft.pptx + final.pptx
```

`forge build` does NOT regenerate images that already exist; image-generator
handles its own idempotency.

### Phase 3: Select & iterate

1. User reviews `build/draft.pptx` (every variation as alternate slides,
   labeled `<title> — variant N/M (<model>)`).
2. User picks favorites by either:
   - Editing `selections.json` directly, OR
   - Asking the agent: "for slide hero-shot use the third gpt-image variant".
     The agent updates `selections.json`.
3. Run `forge build --final` to regenerate just `final.pptx` with chosen
   images.
4. Later edits to `slides.md`: rerun `forge build`. Selections **persist by
   slide-id**. Unchanged slides keep their selection. New/changed slides
   re-fan-out variations into `draft.pptx`.

The PPTX is **never the source of truth**. If you hand-edit `final.pptx`,
your edits are lost on next build — that's the contract. Polish in the
spec, not in the PPTX.

## CLI surface

| Command | Purpose |
|---------|---------|
| `forge new <parent> <name>` | Scaffold story.md / slides.yaml / images.yaml / theme.yaml / selections.yaml from templates. |
| `forge validate <folder>` | Lint: slide-ids unique, image_refs resolve, theme exists, layouts valid. |
| `forge migrate <folder>` | Convert a legacy folder (`slides.md` + `selections.json`) to the unified YAML format. |
| `forge images <folder> [--only ref1,ref2]` | Run image-generator only (no PPTX). `--only` restricts to specific image_refs. |
| `forge regen-image <folder> <image_ref>` | Wipe `build/images/<ref>/` (PNGs + prompts.json) and regenerate that ref from scratch. |
| `forge images-status <folder>` | Per-image_ref table: PNGs on disk vs expected. |
| `forge build <folder> [--draft\|--final\|--both] [--skip-images\|--text-only] [--only ref1,ref2]` | Default both. `--skip-images` / `--text-only` skips image-gen entirely (text-only iteration). `--only` restricts image-gen to a subset. |
| `forge select <folder> <slide-id> <model> <variation> <instance>` | Update selections.yaml. |
| `forge status <folder>` | Per-slide table: built? selected? changed since last build? |

If `final.pptx` is open in PowerPoint when you run `forge build`, the
renderer falls back to writing `final-updated.pptx` (or
`final-updated-2.pptx`, …) so the build never fails with a low-level
`PermissionError`. A friendly message is printed to stderr.

### Targeted regeneration

```powershell
# Just want to retry one image after editing its description?
forge regen-image .\my-talk hero-shot

# Or generate two specific refs without touching the rest?
forge images .\my-talk --only hero-shot,closing-photo
```

### Text-only iteration

Tweaking copy without touching images?

```powershell
forge build .\my-talk --text-only       # alias for --skip-images
```

Image-generator is not invoked; existing PNGs in `build/images/` are reused.

Running pattern (same as image-generator — `uv --directory` changes CWD,
so always pass absolute paths and explicit working-dir flags):

```powershell
uv --directory <skill-dir> sync                          # one-time bootstrap
uv --directory <skill-dir> run forge new (Resolve-Path .) my-talk
uv --directory <skill-dir> run forge validate (Resolve-Path .\my-talk)
uv --directory <skill-dir> run forge build (Resolve-Path .\my-talk)
```

## Authoring rules of thumb

- **One slide-id per slide; never rename**. Renaming loses the selection
  and forces re-pick.
- **Keep `common_requirements` in images.yaml opinionated** — vague briefs
  produce vague variations. Treat it as a system prompt.
- **Prefer `bullets-with-image` and `full-bleed-image` over plain
  `bullets`** — text-only slides are forgettable.
- **Cap slide count at ~25** for a 30-min talk; ~10 for a lightning
  presentation. Confirm with the user before going long.
- **Generate ≤ 30 image renders in one batch** without confirming
  cost/quota. A 10-slide deck × 4 variations × 2 instances × 2 models = 160
  images — slow and expensive.

## Common failure modes

- `forge validate` reports unknown `image_ref` → the slide refers to an
  `images[].name` not present in images.yaml. Add the entry or fix the
  reference.
- `forge validate` reports duplicate `slide-id` → rename one. (Will lose
  any selection on the renamed slide.)
- Image generation 401/403/429 → see image-generator's failure-modes
  table; it's the same Foundry backend.
- `forge build` reports "template.pptx missing layout 'two-column'" → the
  user's template is missing one of the named layouts; either add the
  layout in PowerPoint or change the slide's `layout:` to a supported one.

## What this skill does NOT do

- Edit existing PPTX files outside the spec model.
- Render videos / animations / transitions.
- Produce PDF directly (use the `forge build` PPTX → LibreOffice → PDF
  pipeline if needed).
- Manage image-generator's Azure auth / .env (delegates to that skill).

## References

- [`references/SLIDES_FORMAT.md`](references/SLIDES_FORMAT.md) — full
  slides.md grammar and layout enum.
- [`references/WORKFLOW.md`](references/WORKFLOW.md) — detailed
  ideation-to-final flow with example transcripts.
- [`references/UPDATE_MODEL.md`](references/UPDATE_MODEL.md) — how
  selections persist across rebuilds.
- [`assets/examples/example-talk/`](assets/examples/example-talk/) — full
  worked example.
- [`scripts/run.md`](scripts/run.md) — invocation cheat-sheet.
