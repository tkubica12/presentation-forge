# presentation-forge

Build presentations by **talking to an agent**. You describe what you
want; the agent maintains a small set of plain-text files that fully
describe the deck, and renders the final `.pptx` from them. The PPTX is
just a build artifact — your real source of truth is the text.

This is not a CLI you run by hand. It's a set of agent skills your AI
assistant uses on your behalf. You stay in the conversation; the agent
edits the files, generates the images, and produces the deck.

## What's in this repo

Three [`agentskills.io`](https://agentskills.io)-compatible skills your
agent installs once and then uses together:

| Skill | What it does for you |
|-------|----------------------|
| [`presentation-forge`](./skills/presentation-forge) | Owns the deck spec (`story.md`, `slides.yaml`, `images.yaml`, `theme.yaml`, `selections.yaml`) and produces draft + final PPTX. |
| [`image-generator`](./skills/image-generator) | Generates AI image variants from a YAML brief using Azure AI Foundry models. |
| [`pptx-render`](./skills/pptx-render) | Composes slides onto your corporate `.potx`/`.pptx` template so the deck looks native. |

Install once:

```
gh skill install tkubica12/presentation-forge presentation-forge
gh skill install tkubica12/presentation-forge image-generator
gh skill install tkubica12/presentation-forge pptx-render
```

Image generation needs Azure AI Foundry credentials — the
`image-generator` skill walks you through `.env` setup.

## How a deck gets built — the conversation flow

Each step is a chat with the agent. Each step ends with a file you and
the agent can both read and edit. You never need to know the CLI; the
agent handles it.

### 1. The story — `story.md`

You tell the agent what the talk is about. The agent asks a handful of
clarifying questions and writes a tight prose narrative.

> *"Help me draft a 10-minute internal pitch on Aurora Coffee's Q3
> launch. Audience is execs. Goal is to get budget approval."*

`story.md` is **prose, not slides** — audience, central claim, the 3–5
beats that carry it, the call to action, any sources to ground in.
You're done when you can read it aloud and it flows.

### 2. The slide structure — `slides.yaml`

You ask the agent to turn the story into slides. Together you decide,
slide by slide:

- **Layout** — `cover` (hero title), `bullets`, `bullets-with-image`,
  `full-bleed-image`, `quote`, `two-column`, `image-grid`, … Discuss
  what fits each beat.
- **Title and bullets** — short and scannable; the agent drafts, you
  push back.
- **Where images belong** — not every slide needs art. Decide which
  slides carry a visual and give that visual a stable name (an
  `image_ref`).
- **Speaker notes** — if you want any; they end up in PPTX notes.

Iterate in chat: *"slide 4 should be a comparison, not bullets"*,
*"drop slide 7, merge into 8"*, *"add a quote slide after the intro"*.

### 3. The image briefs — `images.yaml`

For every `image_ref` you used, you tell the agent what the image
should look like. Three layers:

- **General visual style** at the top (`common_requirements`) —
  palette, mood, lighting, framing. Treat this as the "house style"
  for the whole deck. Spend time here; it affects every image.
- **Per-image description** — what *this specific* image shows.
- **Variations** — 2–4 alternate takes per image so you have something
  to choose between (e.g. *"close-up vs wide shot vs top-down"*).

The agent fans these out across multiple AI models so you typically get
several candidates per image.

### 4. The draft deck

You ask the agent to build the draft. It generates all the images
(cached, resumable — fine to interrupt and continue later) and produces
**`build/draft.pptx`**. The draft contains **every image variant as a
separate slide**, each labeled with its variant tag.

You open `draft.pptx` in PowerPoint and review.

### 5. Picking variants — `selections.yaml`

You walk through the draft and tell the agent which variant you want
per slide. Easiest way: copy the variant label from the draft slide and
paste it into chat.

> *"For 'hero', take the gpt-image-1 v02 i01 variant."*
> *"For 'pour-over', none of these work — make it warmer, top-down, less
> clinical, and regenerate."*
> *"Slide 4's title is too long — tighten it."*

The agent handles each kind of feedback differently:

| You say | Agent does |
|---|---|
| Pick a specific variant | Updates `selections.yaml`. |
| Reject all variants for one image | Edits that image's brief in `images.yaml`, regenerates *just that one*. |
| Tweak slide text | Edits `slides.yaml`, rebuilds the draft (no image regen needed). |

Loop until you're happy. Selections persist across rebuilds — unchanged
slides keep their pick.

### 6. The final deck

You ask the agent to build final.

`build/final.pptx` is rendered with the picked variant per slide,
composed onto your corporate template. Layouts, masters, fonts, colors,
decorative shapes — all inherited from the template. The deck looks
native to your brand.

If you have `final.pptx` already open in PowerPoint, the agent writes
to `final-updated.pptx` instead so nothing is lost.

## What lives in each file

```
my-talk/
  story.md          # the narrative, in prose
  slides.yaml       # ordered slides: layout, title, bullets, image_ref, notes
  images.yaml       # image briefs: house style + per-image + variations
  theme.yaml        # which corporate template + brand tokens to use
  selections.yaml   # your picked variant per slide
  build/
    images/         # generated images (cached)
    draft.pptx      # all variants — for review
    final.pptx      # the deck you present
```

Everything except `build/` is text you can read, version-control, and
hand off. The agent is the one that *writes* these files, but you can
always open them and read what's there.

## Using your corporate template

Drop a `.potx` or `.pptx` template anywhere on disk (we suggest
`.templates/` — gitignored) and tell the agent. It records the path
plus layout-name mappings in `theme.yaml`:

```yaml
template: ../../path/to/your-corporate-template.potx
layouts:
  cover: "Title Slide 1"
  bullets: "Title and Content"
  quote: "Quote"
  full-bleed-image: "Photo full bleed lower title"
  # ... one entry per layout you use
metadata:
  author: "you@company.com"
```

Layout names must match what's in the template (open it in PowerPoint →
View → Slide Master to see them). The agent will help you map them.

## A few principles worth knowing

- **The PPTX is disposable.** If you hand-edit `final.pptx`, your edits
  are lost on next build. Tell the agent to change the spec instead.
- **Slide IDs are stable.** Don't ask the agent to rename a slide-id;
  selections are keyed by it. Edit the *content* of a slide freely.
- **Iterate cheaply.** Tweaking text doesn't re-run image generation.
  Tweaking one image doesn't re-run the others. The agent has commands
  for both.
- **Be opinionated about house style.** Vague briefs in `images.yaml`
  produce vague images. Spend time on `common_requirements`.

## License

MIT — see [`LICENSE`](./LICENSE).

The `pptx-render` skill is a verbatim vendored copy of
[`microsoft/hve-core`](https://github.com/microsoft/hve-core) (also
MIT, © Microsoft Corporation) — see `skills/pptx-render/NOTICE` and
`skills/pptx-render/LICENSE-microsoft` for provenance.

> This repo does **not** vendor Anthropic's `pptx` skill. That skill's
> license forbids redistribution outside Anthropic's services.
