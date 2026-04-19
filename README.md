# presentation-forge

Opinionated agent-driven framework for building presentations from text.
Story and structured slide specs are the **source of truth**; the PPTX is
just a build artifact regenerated from those specs each time.

This repo ships two `agentskills.io`-compatible skills:

# presentation-forge

Opinionated agent-driven framework for building presentations from text.
Story and structured slide specs are the **source of truth**; the PPTX is
just a build artifact regenerated from those specs each time.

This repo ships three `agentskills.io`-compatible skills:

| Skill | Purpose |
|-------|---------|
| [`image-generator`](./skills/image-generator) | Generate image series (with variations + instances) from a YAML brief, using Azure AI Foundry models (MAI-Image-2 + gpt-image-1.5) with Entra auth, parallelism, and retry. |
| [`presentation-forge`](./skills/presentation-forge) | Author + build the deck. Owns `story.md`, `slides.md`, `images.yaml`, `theme.yaml`, `selections.json`. Calls `image-generator` for visuals; calls `pptx-render` to produce the `.pptx`. |
| [`pptx-render`](./skills/pptx-render) | Vendored copy of [`microsoft/hve-core`](https://github.com/microsoft/hve-core)'s PowerPoint renderer. Composes slides onto your corporate `.pptx`/`.potx` template (masters, layouts, fonts, colors all inherited). |

## Agentic workflow (the short version)

You drive the agent in **English**; the agent maintains a folder of
plain-text files. Each step has a "ready when" exit condition before
moving on.

```
folder/
├── story.md          # ← step 1
├── slides.md         # ← step 2
├── images.yaml       # ← step 2 (image briefs)
├── theme.yaml        # ← created once per template
├── selections.json   # ← step 4 (which image variant per slide)
└── build/
    ├── images/...    # ← step 3 outputs
    ├── draft.pptx    # ← step 3 (one slide per image variant)
    └── final.pptx    # ← step 5
```

### Step 1 — Co-author the story
> *"Help me draft a story for a 10-min internal pitch on Aurora Coffee's Q3 launch. Audience is execs. Goal is to get budget approval."*

The agent asks ~3-5 clarifying questions (audience, tone, key claim,
constraint, call-to-action) and writes `story.md` — a tight prose
narrative, **not** slide bullets. **Ready when:** you can read it aloud
and it flows.

### Step 2 — Co-author slides + image briefs
> *"Now turn that story into slides. Use ~8 slides, mostly bullets-with-image. Quote slide for the founder line."*

The agent produces:
- **`slides.md`** — one YAML block per slide (`title`, `layout`, `bullets`, `image_ref`, `notes`). 10 layouts to choose from (`title`, `bullets`, `bullets-with-image`, `full-bleed-image`, `quote`, `two-column`, `image-grid`, …). See [`SLIDES_FORMAT.md`](./skills/presentation-forge/references/SLIDES_FORMAT.md).
- **`images.yaml`** — one entry per `image_ref` with the prompt for the image generator (style, subject, mood, negative prompts).

Iterate in chat: *"slide 4 should be a comparison, not bullets"*, *"the hero image should feel cinematic, not stocky"*. **Ready when:** `forge validate` passes (no missing fields, every `image_ref` resolves).

### Step 3 — Generate images and a draft deck
> *"Generate images and build the draft."*

Agent runs:

    forge build <folder>

This: (a) fans out the prompts to `image-generator` (default: 3 models × 3 variations × 1 instance ≈ 9 candidates per `image_ref`); (b) renders **`draft.pptx`** with **one slide per variant** for image-bearing slides (so slide "hero" appears 9 times, each labeled with model+v+i).

### Step 4 — Review and decide, per image
Open `draft.pptx`, look at the variants, then tell the agent your verdict for each slide. Three kinds of feedback:

| You say | Agent does |
|---|---|
| *"For 'hero', pick the gpt-image-1 v02 i01."* | Records into `selections.json`. |
| *"None of the 'pour-over' variants work — make it warmer, less clinical, top-down angle."* | Edits `images.yaml`'s `pour-over` prompt. Re-runs image-gen for that ref only. |
| *"Slide 4's title is too long; tighten it."* | Edits `slides.md` for that slide. |

Loop step 3+4 until you're happy.

### Step 5 — Build the final deck
> *"Build final."*

    forge build <folder>

Renders **`final.pptx`** with the selected variants composed onto your
corporate template (the `.potx`/`.pptx` you set in `theme.yaml`'s
`template:` key). Layouts, masters, fonts, colors are all inherited —
the deck looks native to the template.

Editing any spec file and rebuilding is **non-destructive** for image
selections — `selections.json` survives.

---

## Installing the skills

Using the GitHub CLI (preview):

    gh skill install tkubica12/presentation-forge image-generator
    gh skill install tkubica12/presentation-forge presentation-forge
    gh skill install tkubica12/presentation-forge pptx-render

Or clone and run from this checkout — each skill is a standalone uv
project under `skills/<skill>/`. See each skill's `SKILL.md` for usage.

## Local development

Each skill is independent:

    cd skills/image-generator    && uv sync
    cd skills/presentation-forge && uv sync
    cd skills/pptx-render        && uv sync

Run a smoke test of the example talk (no Azure required when
`--skip-images` is passed):

    cd skills/presentation-forge
    uv run forge validate ./assets/examples/example-talk
    uv run forge build    ./assets/examples/example-talk --skip-images
    uv run pytest

For full image generation, set up `.env` per
`skills/image-generator/SKILL.md` and drop `--skip-images`.

## Using a corporate template

Drop a `.potx` or `.pptx` template anywhere on disk (we suggest
`.templates/` — it's gitignored), then point `theme.yaml` at it:

```yaml
template: ../../path/to/your-corporate-template.potx
layouts:
  title: "Title Slide 1"
  bullets: "Title and Content"
  quote: "Quote"
  full-bleed-image: "Photo full bleed lower title"
  # ... map every layout you use to a layout name in the template
metadata:
  author: "you@company.com"
```

Layout names must match exactly (open the template in PowerPoint → View
→ Slide Master to discover them). The renderer inherits all template
masters, layouts, fonts, colors, and decorative shapes.

## License

MIT — see [`LICENSE`](./LICENSE).

The `pptx-render` skill is a verbatim vendored copy of
[`microsoft/hve-core`](https://github.com/microsoft/hve-core) (also MIT,
© Microsoft Corporation) — see `skills/pptx-render/NOTICE` and
`skills/pptx-render/LICENSE-microsoft` for provenance.

> Note: this repo does **not** vendor Anthropic's `pptx` skill. That
> skill's license forbids redistribution outside Anthropic's services.
