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
briefs are the source of truth; the PPTX is a build artifact, always
regenerated from spec. Hand-edits to the PPTX are lost on next build —
that's the contract.

**Invoke when**: the user wants to author or iterate on a presentation
collaboratively (narrative → slides → AI images → final deck).
**Do NOT invoke** for one-off edits to a PPTX the user already owns.

## Folder layout

```text
talks/
  my-talk/
    story.md          # free-form narrative, audience, goals, references
    slides.yaml       # ordered slides (stable slide-ids + layout + content)
    images.yaml       # image briefs (consumed by image-generator skill)
    theme.yaml        # template path + brand tokens
    selections.yaml   # per-slide chosen image variant (state)
    build/
      images/         # generated PNGs (cached, idempotent)
      draft.pptx      # every variation as alternate slides — for review
      final.pptx      # one image per slide based on selections.yaml
```

Everything except `build/` is human-edited and committed.

Recommended shared-repo layout:

- `talks/` — reusable talk blueprints
- `deliveries/` — concrete event / customer / internal decks
- `pptx-assets/design-templates/` — corporate `.potx` / `.pptx` templates
- `pptx-assets/slide-libraries/` — reserved for future reusable source slides
- `pptx-assets/brand-assets/` — logos, icons, and source graphics

## Setup (once per machine)

```powershell
gh skill install tkubica12/presentation-forge presentation-forge
gh skill install tkubica12/presentation-forge image-generator
gh skill install tkubica12/presentation-forge pptx-render
```

Image generation also needs Azure AI Foundry creds in `image-generator`'s
`.env` (see that skill's docs).

## End-to-end flow

The agent walks the user through these phases. Stay in each phase until
the user is happy before moving on.

### 1. Narrative — `story.md`

Co-author the story first, in plain markdown. The scaffold has section
headings: **Audience**, **Goal**, **Narrative arc** (Hook → Tension →
Insight → Resolution → Call to action), **Key messages**, **References**,
and an optional **Localization** section.

Ask the user:
- Who is the audience and what's the takeaway in one sentence?
- 3–5 supporting beats?
- Any sources / URLs to ground in?
- Will the slides be presented in a different language than this file?
  If yes, fill in `## Localization`: target language, tone, terms to
  keep untranslated, translation philosophy. The agent reads it when
  producing slides, image briefs, and speaker notes.

Scaffold the folder once the story is roughly there:

```powershell
forge new talks my-talk
```

### 2. Slide structure — `slides.yaml`

Turn `story.md` into an ordered slide list. For each slide, discuss with
the user:
- **layout** — pick from the supported set (see
  [`references/SLIDES_FORMAT.md`](references/SLIDES_FORMAT.md)). Notable
  layouts: `cover` (hero title), `quote` (centered pull-quote),
  `bullets-with-image`, `full-bleed-image`, `two-column`.
- **title + bullets / body** — keep bullets short and scannable.
- **image_ref** — name of the image brief this slide uses (defined in
  `images.yaml`). Decide *which* slides actually need an image; text-only
  slides are forgettable but not every slide needs art.
- **speaker_notes** — optional; written into the PPTX notes pane.

Slide IDs are stable kebab-case strings. **Never rename a slide-id** —
selections are keyed by it.

### 3. Image briefs — `images.yaml`

For every `image_ref` used by a slide, define an entry with:
- **common_requirements** at the top of the file — a "system prompt"
  for visual style (palette, mood, framing). Treat as opinionated.
- **per-image `description`** — what this specific image shows.
- **variations** — usually 4–8 variants per image so the user can pick.
  Default backend is `gpt-image-2`; for presentation work prefer
  `size: 3840x2160` in `images.yaml` unless the image is intentionally
  square (`2048x2048`).

Schema is the same one image-generator consumes — see
[`../image-generator/references/YAML_SCHEMA.md`](../image-generator/references/YAML_SCHEMA.md).

Cap renders per batch (~30) before confirming cost. With the new defaults,
a 10-slide deck × 8 variations × 1 instance × 1 model = 80 images.

### 4. Validate + draft

```powershell
forge validate <folder>
forge images   <folder>      # generates all images, idempotent + resumable
forge build    <folder>      # writes build/draft.pptx + build/final.pptx
```

`draft.pptx` contains every image variation as alternate slides labeled
`<title> — variant N/M (<model>)`. Open it and review.

### 5. User picks variants → agent writes `selections.yaml`

The user reviews `draft.pptx` and tells the agent which variant they
want for each slide — typically by **copying the variant label text from
the draft slide** (e.g. *"Hero shot — variant 3/4 (gpt-image)"*). The
agent then updates `selections.yaml` accordingly:

```powershell
forge select <folder> <slide-id> <model> <variation> <instance>
```

…or edits `selections.yaml` directly. Selections persist by slide-id
across rebuilds.

### 6. Render final

```powershell
forge build <folder> --final
```

Re-renders `final.pptx` with the chosen variant per slide. If
`final.pptx` is open in PowerPoint, the renderer writes
`final-updated.pptx` instead of crashing.

## Iteration shortcuts

```powershell
# Tweak text only — skip image-gen entirely:
forge build <folder> --text-only

# Re-render one image after editing its prompt:
forge regen-image <folder> hero-shot

# Generate / refresh just a subset:
forge images <folder> --only hero-shot,closing-photo
forge build  <folder> --only hero-shot

# Inspect image-gen status:
forge images-status <folder>
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `forge new <parent> <name>` | Scaffold story.md / slides.yaml / images.yaml / theme.yaml / selections.yaml. |
| `forge validate <folder>` | Lint: slide-ids unique, image_refs resolve, theme exists, layouts valid. |
| `forge migrate <folder>` | Convert a legacy `slides.md` + `selections.json` folder to YAML. |
| `forge images <folder> [--only ref1,ref2]` | Run image-generator only (no PPTX). |
| `forge regen-image <folder> <image_ref>` | Wipe `build/images/<ref>/` and regenerate that ref. |
| `forge images-status <folder>` | Per-image_ref table: PNGs on disk vs expected. |
| `forge build <folder> [--draft\|--final\|--both] [--skip-images\|--text-only] [--only refs]` | Default `--both`. |
| `forge select <folder> <slide-id> <model> <variation> <instance>` | Update selections.yaml. |
| `forge status <folder>` | Per-slide table: built? selected? changed since last build? |

Run pattern (always pass absolute paths because `uv --directory` changes CWD):

```powershell
uv --directory <skill-dir> sync                          # one-time bootstrap
uv --directory <skill-dir> run forge build (Resolve-Path .\my-talk)
```

## Common failure modes

- **Unknown `image_ref`** → slide references an `images[].name` not in
  `images.yaml`. Add it or fix the reference.
- **Duplicate `slide-id`** → rename one (loses that slide's selection).
- **Template missing layout** → user's `template.pptx` lacks one of the
  named layouts; add it in PowerPoint or change the slide's `layout:`.
- **Image-gen 401/403/429** → see image-generator's docs (same Foundry
  backend, same fixes).

## What this skill does NOT do

- Edit existing PPTX files outside the spec model.
- Render videos / animations / transitions.
- Produce PDF directly (use `forge build` PPTX → LibreOffice).
- Manage image-generator's Azure auth (delegates to that skill).

## References

- [`references/SLIDES_FORMAT.md`](references/SLIDES_FORMAT.md) — slides.yaml grammar + layout enum.
- [`references/WORKFLOW.md`](references/WORKFLOW.md) — detailed ideation-to-final flow.
- [`references/UPDATE_MODEL.md`](references/UPDATE_MODEL.md) — how selections persist across rebuilds.
- [`assets/examples/example-talk/`](assets/examples/example-talk/) — worked example.
- [`scripts/run.md`](scripts/run.md) — invocation cheat-sheet.
