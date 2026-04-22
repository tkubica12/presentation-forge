# Workflow — ideation to final

The presentation-forge workflow is a **conversation, not a wizard**.
The agent walks the user through five artifacts in order, with a clear
gate at each transition. After the first build the loop is iterate →
rebuild → re-pick.

The five artifacts:

| File | Phase | What it holds |
|------|-------|---------------|
| `story.md`       | 1 | Free-form narrative; the source of source. |
| `slides.yaml`    | 2 | Ordered slides: layout + content + image_ref. |
| `images.yaml`    | 3 | Per-image briefs (style, description, variations). |
| `theme.yaml`     | 4 | Corporate template path + layout-name mapping. |
| `selections.yaml`| 6 | User's chosen variant per image-bearing slide. |

`forge new <parent> <name>` scaffolds all five from templates so the
agent can co-author them in turn rather than start from scratch.

## Phase 1 — Story (`story.md`)

Ask the user, in this order:

1. **Audience.** Seniority, context, what they care about.
2. **Goal.** What should the audience think / feel / do after the talk?
3. **Narrative arc.** Hook → Tension → Insight → Resolution → Call to
   action. Confirm 3–5 supporting beats that carry it.
4. **Key messages.** 2–4 takeaways stated as one-line claims.
5. **References.** URLs, papers, internal docs, local notes — anything
   the agent should ground the deck in.
6. **Time budget.** 5 / 15 / 30 / 60 min → roughly 5 / 10 / 15 / 25
   slides.
7. **Output language (optional).** If the slides will be presented in
   a language different from `story.md` itself, fill in the
   `## Localization` section: target language, tone, terms to keep
   untranslated, translation philosophy, phrasing preferences. The
   agent reads this when producing slides, image briefs, and speaker
   notes.

The scaffolded `story.md` already has these section headings (Audience
/ Goal / Narrative arc / Key messages / References / Localization).
Fill them in as free-form markdown — prose, lists, quotes, links.

**Do not generate slides yet.** Confirm the story with the user first.

## Phase 2 — Slides (`slides.yaml`)

Translate beats into slides. For each beat plan 1–3 slides (intro,
point, conclusion of the beat). Always start with a `cover` slide; use
`section-divider` between major beats; end with a takeaway slide and
optionally `appendix-references`.

For each slide, ask the user (or propose and let them push back):

- **Layout** — pick from the supported set (see
  [`SLIDES_FORMAT.md`](./SLIDES_FORMAT.md)).
- **Title.**
- **Body** — bullets, a hero image, a quote, or a side-by-side
  comparison.
- **`image_ref`** — only for slides that genuinely need a visual.
- **Speaker notes** — what the user will say but the slide won't show.

Use stable `slide-id` values from the start — don't auto-number; use
semantic names (`opening-hook`, `pillar-quality`, `pillar-craft`, …).
They survive reordering and become selection keys. **Never rename a
slide-id** later.

Confirm the slide list with the user before moving on.

## Phase 3 — Images (`images.yaml`)

For every `image_ref` used in `slides.yaml`:

- Add an entry with the same `name` as the `image_ref`.
- Lift `common_requirements` from the brand / mood established in
  `story.md`. Treat it as a system prompt for the visual house style.
- Pick `variations_count` based on importance: hero shots get 4–8,
  supporting images 2–4.
- Decide `models`: typically both `MAI-Image-2` and `gpt-image-1.5`
  unless the user has a strong preference.

Schema reference:
[`../../image-generator/references/YAML_SCHEMA.md`](../../image-generator/references/YAML_SCHEMA.md).

Cap renders per batch (~30) before confirming cost: a 10-slide deck ×
4 variations × 2 instances × 2 models = 160 images.

## Phase 4 — Theme (`theme.yaml`)

Point at the user's corporate `.potx`/`.pptx` template (drop in
`.templates/`, gitignored) and map our logical layout names to the
exact layout names that exist in that template. Only map layouts the
deck actually uses. See the README's "Using your corporate template"
section for the why.

## Phase 5 — First build

```powershell
forge validate <folder>
forge images   <folder>     # idempotent + resumable
forge build    <folder>     # writes draft.pptx + final.pptx
```

`draft.pptx` contains every image variation as a separate slide,
labeled `<title> — variant N/M (<model>)`. Open it with the user.

## Phase 6 — Selection (`selections.yaml`)

The user reviews `draft.pptx` and picks a variant per slide.
Easiest UX: copy the variant label from the draft slide and paste
into chat. Three kinds of feedback:

| User says | Agent does |
|---|---|
| "Use gpt-image v02 i01 for `hero`." | `forge select <folder> hero gpt-image-1 02 01` (updates `selections.yaml`). |
| "None of the `pour-over` variants work — make it warmer, top-down, less clinical." | Edits `images.yaml`'s `pour-over`; runs `forge regen-image <folder> pour-over`. |
| "Slide 4's title is too long; tighten it." | Edits `slides.yaml`; rebuilds with `forge build <folder> --text-only`. |

Re-run `forge build <folder> --no-draft` to refresh just `final.pptx`.

## Phase 7 — Iterate

- Edit any spec file, then rebuild.
- Selections persist by `slide-id`. Unchanged slides keep their pick.
  New / changed slides re-fan-out variations into `draft.pptx`.
- Use `forge status <folder>` to see per-slide state at any time.
- Use `forge images-status <folder>` to inspect image-gen progress.
- If `final.pptx` is open in PowerPoint, the renderer writes
  `final-updated.pptx` instead of failing.
