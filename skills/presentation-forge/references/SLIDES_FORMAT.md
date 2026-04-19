# slides.md format

`slides.md` is a markdown file containing one or more slides separated by
lines of three dashes (MARP convention). Each slide is a YAML frontmatter
block followed by an optional markdown body (currently unused — all
authoring is in the frontmatter to keep parsing deterministic).

## Slide block grammar

```markdown
---
slide-id: <kebab-case unique id>     # required, stable across renames
layout: <layout-enum value>          # required (see below)
title: "<string>"                    # required for most layouts
subtitle: "<string>"                 # optional, title layout only
bullets:                              # required for bullets / bullets-with-image / two-column
  - First bullet
  - Second bullet
body: |                              # quote / appendix-references / callout
  Free-form text body.
image_ref: <images[].name>            # references an entry in images.yaml
image_position: left|right|full       # bullets-with-image / full-bleed-image
notes: |                             # speaker notes (multi-line)
  Talking points the user reads but the audience doesn't see.
---
```

## Slide layout enum

| layout | required fields | optional fields | description |
|--------|-----------------|-----------------|-------------|
| `title`               | `title`           | `subtitle`, `image_ref` | Cover slide. |
| `section-divider`     | `title`           | `subtitle`              | Section break, large text on accent background. |
| `bullets`             | `title`, `bullets`| `notes`                 | Plain bullet list, text-only. |
| `bullets-with-image`  | `title`, `bullets`, `image_ref` | `image_position` (default `right`) | Two-column: bullets + image. |
| `full-bleed-image`    | `image_ref`      | `title`, `subtitle`     | Edge-to-edge image, optional title overlay. |
| `two-column`          | `title`, `bullets` (length 2 → cols) | `notes` | Side-by-side text columns; each bullet becomes a column. |
| `quote`               | `body`            | `subtitle` (attribution) | Centered quote pull. |
| `comparison`          | `title`, `bullets` (length 2) | `notes` | Before/after, pros/cons. |
| `image-grid`          | `title`, multi `image_refs` (list) | `notes` | 2x2 or 2x3 grid of variant images for review only — not typically authored, used in `draft.pptx`. |
| `appendix-references` | `title`, `body`   |                         | Auto-emitted from story.md citations if requested. |

## Stable slide-ids

`slide-id` is the **primary key** for selection persistence. Rules:

- Kebab-case, ASCII only, must match `^[a-z0-9][a-z0-9-]*$`.
- Unique within a slides.md file.
- **Never reuse or rename** unless you intend to lose the entry's
  selection. `forge validate` warns on suspicious renames (slide-id removed
  + new slide-id added with similar content).

## image_ref resolution

`image_ref` is the `name` field of an entry in the same folder's
`images.yaml`. The image-generator skill produces files at
`build/images/<image_ref>/<model>/<image_ref>_v<NN>_i<NN>.png`. The
renderer picks one of those for `final.pptx` based on
`selections.json[<slide-id>]`, or all of them (cloning the slide N times)
for `draft.pptx`.

## Example

```markdown
---
slide-id: title
layout: title
title: "Aurora Coffee — Brand Story"
subtitle: "Q3 2026 launch deck"
notes: |
  Open with the founder anecdote.
---

---
slide-id: hero
layout: full-bleed-image
title: "A morning ritual"
image_ref: morning-ritual
notes: |
  Pause; let the image breathe.
---

---
slide-id: pillars
layout: bullets-with-image
title: "Three pillars"
bullets:
  - Quality beans, single-origin
  - Slow craft, fast service
  - Designed for ritual
image_ref: pour-over-detail
image_position: right
notes: |
  Tie each pillar to a customer story.
---
```

## Optional `extra_elements:` (advanced passthrough)

For one-off shapes that the editorial layer (title / bullets / image_ref)
cannot express — e.g., a sponsor logo strip, a watermark, a decorative
divider — a slide may carry an `extra_elements:` list. Each list item is
a dict that is **spliced verbatim** into the renderer's `elements:` array
and drawn on top of the adapter-generated content. Validity is the
author's responsibility.

The element schema is the one consumed by the vendored
`microsoft/hve-core` PowerPoint skill (see
`skills/pptx-render/element-types-template.md` for the full grammar).
Common element types are `textbox`, `image`, `shape`, `line`, and
`table`. Coordinates are in **inches** on a 16:9 canvas
(13.333" × 7.5").

```markdown
---
slide-id: title
layout: title
title: "Aurora Coffee"
subtitle: "Q3 launch creative direction"
extra_elements:
  - type: textbox
    left: 0.4
    top: 7.05
    width: 12.5
    height: 0.35
    text: "Confidential — internal review only"
    font_size: 9
    font_italic: true
  - type: shape
    shape_type: rectangle
    left: 0
    top: 7.46
    width: 13.333
    height: 0.04
    fill: "#0078D4"
---
```

Reach for this only when the editorial fields can't carry the intent —
otherwise prefer keeping slides expressive at the editorial layer.

