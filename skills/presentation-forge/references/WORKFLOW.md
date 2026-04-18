# Workflow — ideation to final

The presentation-forge workflow is a **conversation, not a wizard**. The
agent walks the user through four artifacts, in order, with a clear gate
at each transition.

## Phase 1: Story (`story.md`)

Ask the user, in this order:

1. Who is the audience? (Their seniority, their context, what they care
   about.)
2. What is the central thesis in one sentence?
3. What 3-5 supporting beats carry it?
4. What references / sources should the agent ground in? (URLs, papers,
   internal docs.)
5. What's the time budget? (5/15/30/60 min → maps to 5/10/15/25 slides.)

Capture answers as free-form markdown in `story.md`. Include:

- A `## References` section with bullets per source (URL + 1-line note).
- A `## Audience` paragraph.
- A `## Thesis` paragraph.
- A `## Beats` ordered list.

Do **not** generate slides yet. Confirm the story with the user first.

## Phase 2: Slides (`slides.md`)

Now translate beats into slides. For each beat:

- 1-3 slides typically (intro / point / conclusion of the beat).
- Always start the deck with a `title` slide.
- Use `section-divider` between major beats.
- End with a takeaway slide and optionally `appendix-references`.

For each slide, ask the user (or propose and let them push back):

- What's the title?
- 3-5 bullet points OR a hero image OR a quote OR a side-by-side
  comparison?
- Speaker notes (what the user will say but slide won't show).

Use stable `slide-id` values from the start — don't auto-number; use
semantic names (`opening-hook`, `pillar-quality`, `pillar-craft`, etc.)
because they survive reordering and become selection keys.

Confirm slide list with the user before moving on.

## Phase 3: Images (`images.yaml`)

For each slide that needs an image:

- Add an entry to `images.yaml` with the same `name` as the `image_ref`
  used in slides.md.
- Lift `common_requirements` from the brand / mood established in
  story.md.
- Pick `variations_count` based on importance: hero shots get 4-8,
  supporting images 2-4.
- Decide `models`: typically both `MAI-Image-2` and `gpt-image-1.5`
  unless the user has a strong preference.

The image-generator skill's
[`YAML_SCHEMA.md`](../../image-generator/references/YAML_SCHEMA.md) is the
authoritative reference.

## Phase 4: Theme (`theme.yaml`)

Pick a starter template from `assets/templates/` (or the user supplies one).
Set brand tokens. This is usually quick.

## Phase 5: First build

```powershell
forge validate
forge build
```

Open `build/draft.pptx`. Walk through with the user; capture preferred
variants per slide.

## Phase 6: Selection

Either:

- The user opens `selections.json` and edits directly.
- Or the agent updates it via `forge select <slide-id> <model>
  <variation> <instance>`.

Re-run `forge build --final` to produce `final.pptx`.

## Phase 7: Iterate

- Edit story / slides / images as needed.
- Re-run `forge build`. Selections persist by `slide-id`. New / changed
  slides re-fan-out variations into `draft.pptx`. Unchanged slides keep
  their selection in `final.pptx`.
- Use `forge status` to see per-slide state at any time.
