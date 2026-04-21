# slides.yaml format

`slides.yaml` is a YAML file containing a top-level **list of slide dicts**.
The schema is the same one previously used inside the YAML frontmatter
blocks of `slides.md`. The legacy `slides.md` format is still loaded
when present (no breaking change) — but new projects should use
`slides.yaml`. To convert an existing folder, run:

```
forge migrate <folder>
```

A top-level mapping with a `slides:` key is also accepted, e.g.

```yaml
slides:
  - slide-id: title
    layout: title
    title: "My Talk"
```

## Slide entry grammar

```yaml
- slide-id: <kebab-case unique id>          # required, stable across renames
  layout: <layout-enum value>               # required (see below)
  title: "<string>"                         # required for most layouts
  subtitle: "<string>"                      # optional (title / cover / quote attribution)
  bullets:                                  # required for bullets / bullets-with-image / two-column
    - First bullet
    - Second bullet
  body: |                                   # quote / appendix-references / callout
    Free-form text body.
  image_ref: <images[].name>                # references an entry in images.yaml
  image_position: left|right|full           # bullets-with-image / full-bleed-image
  notes: |                                  # speaker notes (multi-line)
    Talking points the user reads but the audience doesn't see.
```

## Slide layout enum

| layout | required fields | optional fields | description |
|--------|-----------------|-----------------|-------------|
| `title`               | `title`           | `subtitle`, `image_ref` | Plain title slide (text only). |
| `cover`               | `title`, `image_ref` | `subtitle`           | **Hero / cover** layout: full-bleed background image with a darkened **left-half panel**, large white title, smaller subtitle. Recommended for deck covers. |
| `section-divider`     | `title`           | `subtitle`              | Section break. |
| `bullets`             | `title`, `bullets`| `notes`                 | Plain bullet list, text-only. |
| `bullets-with-image`  | `title`, `bullets`, `image_ref` | `image_position` (default `right`) | Two-column: bullets + image. |
| `full-bleed-image`    | `image_ref`      | `title`, `subtitle`     | Edge-to-edge image with optional small title strip across the bottom. Use `cover` instead for deck covers. |
| `two-column`          | `title`, `bullets` (length 2 → cols) | `notes` | Side-by-side text columns. |
| `quote`               | `body`            | `subtitle` (attribution) | Centered pull-quote. Renders body high on the slide with smart quotes; em-dash attribution beneath. Opinionated layout — no per-slide knobs. |
| `comparison`          | `title`, `bullets` (length 2) | `notes` | Before/after, pros/cons. |
| `image-grid`          | `title`, multi `image_refs` (list) | `notes` | 2x2 or 2x3 grid for review. |
| `appendix-references` | `title`, `body`   |                         | Auto-emitted from story citations. |

### Quote layout

The quote layout is rendered with explicit textboxes (not template
placeholders) so the body sits visibly **above the vertical center** of
the slide rather than near the bottom. Body font scales with quote
length (36 / 30 / 26 / 22 pt). Attribution is rendered below the body,
prefixed with an em-dash. There are no per-slide overrides — write a
shorter quote if it doesn't fit.

### Cover layout

The cover layout is for deck covers / hero slides. It draws:

1. The full-bleed `image_ref` background image
2. A semi-transparent black rectangle on the **left half** of the slide
3. A large white title (font scales: 44 / 36 / 28 pt)
4. An optional subtitle below the title

```yaml
- slide-id: cover
  layout: cover
  title: "AI in Energy"
  subtitle: "Tomáš Kubica · Microsoft"
  image_ref: hero-image
```

## Stable slide-ids

`slide-id` is the **primary key** for selection persistence. Rules:

- Kebab-case, ASCII only, must match `^[a-z0-9][a-z0-9-]*$`.
- Unique within a `slides.yaml` file.
- **Never reuse or rename** unless you intend to lose the entry's
  selection.

## image_ref resolution

`image_ref` is the `name` field of an entry in the same folder's
`images.yaml`. The image-generator skill produces files at
`build/images/<image_ref>/<model>/<image_ref>_v<NN>_i<NN>.png`. The
renderer picks one of those for `final.pptx` based on
`selections.yaml[<slide-id>]`, or all of them (cloning the slide N times)
for `draft.pptx`.

## Selections (`selections.yaml`)

`selections.yaml` is a flat YAML mapping of `slide-id` → `{model,
variation, instance}`:

```yaml
cover:
  model: gpt-image-1
  variation: 2
  instance: 1
hero:
  model: mai-image-2
  variation: 0
  instance: 0
```

The legacy `selections.json` is still read when present.

## Optional `extra_elements:` (advanced passthrough)

For one-off shapes that the editorial layer cannot express, a slide may
carry an `extra_elements:` list. Each list item is **spliced verbatim**
into the renderer's `elements:` array.

```yaml
- slide-id: title
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
```

The element schema is the one consumed by the vendored
`microsoft/hve-core` PowerPoint skill (see
`skills/pptx-render/element-types-template.md`). Coordinates are in
**inches** on a 16:9 canvas (13.333" × 7.5").
