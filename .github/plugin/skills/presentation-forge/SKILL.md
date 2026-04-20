---
name: presentation-forge
description: >
  Build branded PowerPoint presentations from text. Use this skill when the user wants to
  create, edit, or build a presentation, slide deck, or talk. Triggers include any mention
  of 'presentation', 'slides', 'deck', 'talk', 'pptx', 'PowerPoint', or requests to
  'build slides', 'create a deck', 'generate images for slides', 'review draft', etc.
  Also use when the user wants to co-author a story, define slide structure, generate
  AI images for slides, select image variants, or produce a final branded deck.
---

# presentation-forge

An agentic, text-first presentation builder. You maintain plain-text spec files
(`story.md`, `slides.md`, `images.yaml`, `theme.yaml`, `selections.json`) and
build PowerPoint decks from them using the `forge` CLI.

## How to run forge commands

The forge CLI lives in the repo's `skills/presentation-forge/` directory.
Always run it via uv from that directory:

```powershell
uv --directory <REPO_ROOT>/skills/presentation-forge run forge <command> <project-folder>
```

Where `<REPO_ROOT>` is the git repository root of `presentation-forge` and
`<project-folder>` is the path to the user's presentation project (e.g.
`<REPO_ROOT>/projects/cez`).

### Available commands

| Command | What it does |
|---------|-------------|
| `forge new <parent> <name>` | Scaffold a new presentation folder with starter templates |
| `forge validate <folder>` | Lint the presentation — check for missing fields, unresolved image_refs |
| `forge images <folder>` | Generate AI images only (no PPTX build) |
| `forge build <folder>` | Full build: generate images + render draft.pptx + final.pptx |
| `forge build <folder> --skip-images` | Build PPTX only (skip image generation) |
| `forge build <folder> --skip-images --no-draft` | Build final.pptx only |
| `forge select <folder> <slide-id> <model> <variation> <instance>` | Record which image variant to use for a slide |
| `forge status <folder>` | Show per-slide status (selections, changes, last build) |

## Agentic workflow

Walk the user through these phases in order. Each phase has a gate —
confirm with the user before moving to the next.

### Phase 1: Co-author the story (`story.md`)

Ask the user:
1. Who is the audience?
2. What is the central thesis in one sentence?
3. What 3–5 supporting beats carry it?
4. What references/sources to ground in?
5. Time budget? (5 min → ~5 slides, 15 min → ~10 slides, 30 min → ~15 slides)

Write answers into `story.md`. Include sections: `## Audience`, `## Thesis`,
`## Beats`, `## References`. **Do NOT generate slides yet.** Confirm the
story first.

### Phase 2: Co-author slides + image briefs (`slides.md` + `images.yaml`)

Translate beats into slides. For each slide, define:
- `slide-id` (kebab-case, semantic, stable — never auto-number)
- `layout` (see layout table below)
- `title`, `bullets`/`body`, `image_ref`, `notes`

For each `image_ref`, add a matching entry in `images.yaml` with a descriptive
prompt for the AI image generator.

Run `forge validate <folder>` to check everything resolves.

### Phase 3: Generate images + build draft

Run `forge build <folder>` (or `forge images <folder>` then
`forge build <folder> --skip-images`).

This produces:
- `build/images/` — AI-generated image variants per model
- `build/draft.pptx` — one slide per image variant so user can compare

### Phase 4: Review draft + select winners

User opens `draft.pptx` and gives feedback per slide:
- **Pick a winner**: `forge select <folder> <slide-id> <model> <variation> <instance>`
- **Regenerate**: edit `images.yaml` prompt, re-run `forge images`
- **Edit text**: modify `slides.md`, rebuild

### Phase 5: Build final

Run `forge build <folder> --skip-images` to produce `final.pptx` with
selected image variants composed onto the branded template.

## Slide layouts

| layout | required fields | description |
|--------|----------------|-------------|
| `title` | `title` | Cover slide. Optional `subtitle`, `image_ref`. |
| `section-divider` | `title` | Section break. Optional `subtitle`. |
| `bullets` | `title`, `bullets` | Plain bullet list. |
| `bullets-with-image` | `title`, `bullets`, `image_ref` | Bullets + image side by side. |
| `full-bleed-image` | `image_ref` | Edge-to-edge image with optional title overlay. |
| `two-column` | `title`, `bullets` | Even bullets → left col, odd → right col. |
| `quote` | `body` | Centered quote. Optional `subtitle` for attribution. |
| `comparison` | `title`, `bullets` | Side-by-side comparison (like two-column). |
| `image-grid` | `title`, `image_ref` | 3 images in a filmstrip row. |
| `image-single` | `title`, `image_ref` | Single centered landscape image. |
| `image-duo` | `title`, `image_ref` | Two images side by side. |
| `appendix-references` | `title`, `body` | Reference/citation slide. |

## Theme configuration (`theme.yaml`)

```yaml
template: <path-to-.potx-or-.pptx>   # corporate template
layouts:                                # map layout names to template layout names
  title: "Title Slide 1"
  bullets: "Title and Content"
  # ...
layout_backgrounds:                     # override layout backgrounds (hex color)
  "Photo Slide 1": "FFFFFF"
metadata:
  title: "Deck Title"
  author: "Author Name"
fonts:
  heading: "Segoe UI"
  body: "Segoe UI"
colors:
  background: "FFFFFF"
  foreground: "2A1F18"
  accent: "B8651C"
```

## Image generation config (`images.yaml`)

```yaml
common_requirements: |
  Cohesive style description shared across all images.
variations_count: 2
instances_per_prompt: 1
size: "1024x1024"              # default; override per image
images:
  - name: hero-shot             # matches image_ref in slides.md
    size: "1536x1024"           # landscape override
    description: |
      Detailed prompt for the image generator.
```

Sizes: `1024x1024` (square), `1536x1024` (landscape), `1024x1536` (portrait).

## File structure

```
<project>/
├── story.md           # narrative (phase 1)
├── slides.md          # slide specs (phase 2)
├── images.yaml        # image generation prompts (phase 2)
├── theme.yaml         # template + brand config
├── selections.json    # which variant per slide (phase 4)
└── build/
    ├── images/        # generated images
    ├── draft.pptx     # all variants (phase 3)
    └── final.pptx     # selected variants (phase 5)
```
