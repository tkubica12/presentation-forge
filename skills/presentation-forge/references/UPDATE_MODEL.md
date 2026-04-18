# Update model — selection persistence across rebuilds

The presentation-forge contract: **the PPTX is always rebuilt from spec**.
Hand-edits to `final.pptx` are lost on next `forge build`. State that must
survive lives in two text files: `selections.json` and `build/state.json`.

## `selections.json` (user-facing state)

Keyed by stable `slide-id`:

```json
{
  "title": null,
  "hero": {
    "model": "gpt-image-1.5",
    "variation": 2,
    "instance": 0
  },
  "pillars": {
    "model": "MAI-Image-2",
    "variation": 0,
    "instance": 1
  }
}
```

- `null` → no image chosen yet → `final.pptx` shows a placeholder for that
  slide; `draft.pptx` shows all variations as alternate slides.
- A populated entry → `final.pptx` uses exactly that image; `draft.pptx`
  still shows all variations (until the user is happy and stops looking
  at draft).

User can edit by hand or via `forge select <slide-id> <model> <variation>
<instance>`.

## `build/state.json` (internal cache, do not hand-edit)

```json
{
  "version": 1,
  "slides": {
    "hero": {
      "content_hash": "sha256:abc...",
      "image_ref": "morning-ritual",
      "last_built_draft": "2026-04-18T20:00:00Z",
      "last_built_final": "2026-04-18T20:05:00Z"
    }
  },
  "images": {
    "morning-ritual": {
      "yaml_hash": "sha256:def...",
      "variations_built": 8
    }
  }
}
```

- `content_hash` = sha256 of slide's normalized frontmatter (title +
  bullets + body + image_ref + layout + notes; whitespace-normalized).
- On rebuild, the renderer compares each slide's current hash to
  `state.json`. **Changed** slides are flagged "needs review" — they appear
  in `draft.pptx` with all variations, regardless of any prior selection.
  (Selection is preserved in `selections.json` but the user is nudged to
  reconsider it.)
- `images.yaml_hash` ties variation count to the brief; if the brief
  changes, the image-generator's own cache invalidation kicks in.

## Concrete update scenarios

### Scenario A: user edits a slide's bullets

1. `slides.md` hash for `pillars` changes.
2. `forge build` re-renders `pillars` slide. Image-generator runs but
   skips already-cached images (no image_ref change → no image
   regeneration).
3. `selections.json[pillars]` is preserved → `final.pptx` uses the same
   image.
4. `draft.pptx` still includes `pillars` clones (all variations) so the
   user can re-pick if the new bullets warrant a different image.

### Scenario B: user adds a new slide

1. New `slide-id: cta` appears in slides.md.
2. `forge build`: image-generator generates variations for the new
   `image_ref` (if any). New slide renders with all variations in
   `draft.pptx`. `selections.json[cta]` is `null` → placeholder in
   `final.pptx`.
3. User picks → updates `selections.json` → `forge build --final`.

### Scenario C: user renames a slide-id

1. `forge validate` warns: "slide-id `pillars` removed; new slide-id
   `three-pillars` looks similar". Suggests user run `forge select
   three-pillars ...` to migrate selection.
2. If user proceeds: old selection is dropped; new slide gets full
   variation fan-out in `draft.pptx`.

### Scenario D: user changes images.yaml common_requirements

1. `images.yaml` hash changes. `forge build` invalidates the
   image-generator cache for the affected entries (delete prompts.json + 
   PNGs).
2. New variations generated. **Old selections in `selections.json` may
   point to file paths that no longer exist** (because variation indices
   may shift if `variations_count` changed).
3. `forge validate` checks selection paths exist; flags broken ones; user
   re-picks for those slides.

## Why not edit the PPTX directly?

Tried-and-rejected alternative: keep the PPTX as the source of truth and
diff it on rebuild. Rejected because:

- Binary diffing PPTX is fragile (XML reordering, embedded image hashes).
- "Merge" semantics with user's hand edits + agent's structural edits
  inevitably destroys one or the other.
- Text-first specs are version-controllable, reviewable, and survive tool
  upgrades.

## Why is `final.pptx` still rebuilt from scratch each time?

Yes, even when only one slide changed. Rationale:

- python-pptx assembly of a 25-slide deck takes < 1 second.
- Avoids any merge logic.
- Result is identical bit-for-bit (for the same spec + selections + images),
  so version-control diffs of `final.pptx` are minimal.
