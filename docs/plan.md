# presentation-forge — implementation plan & handoff

> **For the next Copilot CLI session.** Reads as a self-contained handoff:
> what is done, what was decided, what to do next. Pair this with
> `docs/research/powerpoint-tooling-options.md` for the full reasoning
> behind the renderer decision.

---

## 1. Vision (one paragraph)

`presentation-forge` is an opinionated, agent-driven framework for building
**Microsoft-style corporate presentations** where the *story* and a
*structured slide spec* are the source of truth and the `.pptx` is just a
build artifact. A presentation lives in a folder of plain-text files
(`story.md`, `slides.md`, `images.yaml`, `theme.yaml`, `selections.json`).
The agent helps the user co-author those, generates images via the
`image-generator` skill (MAI-Image-2 + gpt-image-1.5 on Azure AI Foundry
with Entra auth), and renders the deck onto the user's Microsoft corporate
template. Edits to the spec re-render cleanly without losing hand-curated
image selections.

---

## 2. Repository layout (current state)

```
presentation-forge/                    # tkubica12/presentation-forge (public, MIT)
├── LICENSE                            # MIT
├── README.md                          # describes both skills + install commands
├── docs/
│   ├── plan.md                        # ← this file
│   └── research/
│       └── powerpoint-tooling-options.md   # 30 KB, 21 footnotes, comparison matrix
└── skills/
    ├── image-generator/               # ✅ DONE — moved verbatim from old repo
    │   ├── SKILL.md
    │   ├── pyproject.toml             # uv project
    │   ├── src/image_generator/{cli.py, foundry.py, prompts.py, ...}
    │   ├── assets/examples/
    │   └── references/
    └── presentation-forge/            # 🟡 SKELETON DONE, renderer needs replacement
        ├── SKILL.md
        ├── pyproject.toml             # uv project
        ├── src/presentation_forge/
        │   ├── cli.py                 # ✅ click: new/validate/images/build/select/status
        │   ├── spec.py                # ✅ Presentation dataclass + load_presentation()
        │   ├── builder.py             # ✅ orchestrates validate→images→render
        │   ├── pptx_render.py         # ⚠️ in-house ~330 lines, "generic corporate";
        │   │                          #    PLAN: replace with hve-core (see §6)
        │   └── templates/             # ✅ scaffolds for `forge new`
        │       ├── story.md.tmpl
        │       ├── slides.md.tmpl
        │       ├── images.yaml.tmpl
        │       └── theme.yaml.tmpl
        ├── assets/examples/example-talk/   # ✅ Aurora Coffee, 6 slides, all major layouts
        ├── references/                # SLIDES_FORMAT.md, WORKFLOW.md, UPDATE_MODEL.md
        └── scripts/run.md             # invocation cheat-sheet
```

---

## 3. What is DONE ✅

### 3.1 Bootstrap & migration
- New repo `tkubica12/presentation-forge` created (public, MIT), pushed.
- `image-generator` skill moved into it verbatim.
- Root `README.md` describing both skills.
- `LICENSE` (MIT), `.gitignore` carried over.

### 3.2 `presentation-forge` skeleton
- `uv` project with `pyproject.toml` + lockfile (10 packages, clean `uv sync`).
- `SKILL.md` with valid frontmatter (`name`, `description ≤1024 chars`, etc.).
- `src/presentation_forge/`:
  - `spec.py` — `Presentation` dataclass, `load_presentation(folder)`, computed
    paths (build_dir, images_dir, state_path, draft_pptx, final_pptx).
  - `cli.py` — click commands: `new`, `validate`, `images`, `build`
    (`--draft|--final|--skip-images`), `select`, `status`.
  - `builder.py` — orchestrates validate / image-gen subprocess / render.
    Shells `uv --directory <image-generator skill> run generate-images …`.
    `SKILL_DIR = Path(__file__).parents[2]` (was buggy as `parents[3]`).
  - `pptx_render.py` — in-house python-pptx renderer for all 10 layouts.
    **Works** but generic-looking; will be replaced. See §6.
  - `templates/*.tmpl` — scaffold sources copied by `forge new`.
- `references/`: `SLIDES_FORMAT.md`, `WORKFLOW.md`, `UPDATE_MODEL.md`.
- `assets/examples/example-talk/` — Aurora Coffee 6-slide deck covering
  `title`, `full-bleed-image`, `bullets`, `bullets-with-image`, `quote`,
  `section-divider`.

### 3.3 Validated (smoke-tested)
- `uv sync` — clean (10 packages).
- `forge validate` on `example-talk` → `OK: 6 slides, 1 image briefs`.
- `forge build --skip-images` → produces openable `draft.pptx` + `final.pptx`,
  6 slides each, re-parsed back successfully.
- `forge status` → per-slide JSON with content hashes.
- `gh skill publish --dry-run` from repo root → both skills validate.
- Initial commit pushed to `tkubica12/presentation-forge` `main`.

---

## 4. What is NOT done ❌

### 4.1 Blocked on user action (housekeeping)
- **Old repo deletion.** `gh repo delete tkubica12/image-generator-skill --yes`
  failed with 403 (token lacks `delete_repo` scope). User must run:
  ```pwsh
  gh auth refresh -h github.com -s delete_repo
  gh repo delete tkubica12/image-generator-skill --yes
  Remove-Item -Recurse -Force C:\git\image-generator-skill
  ```

### 4.2 Renderer quality (the big one — §6)
- ✅ **DONE.** `pptx_render.py` deleted; `microsoft/hve-core` PowerPoint
  skill vendored at `skills/pptx-render/` (commit
  `29a2df1b720ddaedd1e328c0c119550bfff52a86`). Adapter at
  `presentation_forge.render_adapter` translates our `slides.md` model to
  hve-core's `content/slide-NNN/content.yaml` format. Builder shells out
  to hve-core's `build_deck.py` via `uv --directory ../pptx-render run`.
  The Microsoft Azure template (`.templates/Microsoft-Azure-PowerPoint-Template-2604.potx`)
  is normalized to `.pptx` on the fly (content-type rewrite) and the
  produced decks inherit the template's masters, layouts, fonts, and
  colors. See §6 below for the locked-in decisions and the comprehensive
  test suite at `skills/presentation-forge/tests/`.

### 4.3 Future enhancements (deferred, not blocking)
- `forge regen --slide=<id>` for targeted image re-runs.
- Real `template.pptx` instead of programmatic theming.
- Speaker-notes export to handout markdown.
- `forge images --slide=hero --twist="…"` for prompt twist on one image.
- Web preview server (MARP HTML watch).

---

## 5. Decisions already made (don't re-litigate)

| Decision | Rationale | Source |
|---|---|---|
| Two skills in one repo: `image-generator` + `presentation-forge` | Shared schemas, single agent install command, same lifecycle. | Earlier checkpoint. |
| In-house renderer, NOT Anthropic's `pptx` skill | Anthropic's `LICENSE.txt` forbids vendoring even in private repos / outside Anthropic Services. | Earlier checkpoint. |
| `slides.md` is MARP-style markdown with per-slide YAML frontmatter, separated by `---` | Previews in any markdown viewer; stable `slide-id` per slide enables incremental rebuild + selection persistence. | §3 of this plan. |
| `selections.json` keyed by `slide-id` is the source of truth for "which variant goes in `final.pptx`" | Survives spec edits to other slides; renaming a slide-id loses its selection (rare + explicit, acceptable). | §3 of this plan. |
| `image-generator` is invoked via `uv --directory <abs-path> run generate-images …` from `builder.py` | Avoids importing image-generator as a package; preserves its independent uv project. Documented CWD gotcha. | `builder.py`. |
| Default LLM for prompt manipulation in image-generator: `gpt-5.4` | User instruction. | image-generator `prompts.py`. |
| Image-gen Foundry endpoint via `.env` (gitignored): `https://tomaskubica-foundry-resource.services.ai.azure.com`; Entra auth | User instruction. | image-generator `.env.example`. |

---

## 6. THE BIG PENDING DECISION — renderer replacement

### 6.1 Recommendation (from `docs/research/powerpoint-tooling-options.md`)

**Vendor `microsoft/hve-core`'s PowerPoint skill into our repo as a third
skill folder `skills/pptx-render/`.**

- It's MIT‑licensed, Microsoft‑org (ISE / Hypervelocity Engineering).
- Built on `python-pptx` (same library we use).
- Supports `--template corporate-template.pptx` properly via slide‑master
  + layout binding (the thing our current renderer can't do).
- Supports partial rebuild: `--source existing.pptx --slides 3,7,15`
  (perfect fit for our "edit one slide without losing the rest" pattern).
- Supports content extraction from existing decks (round‑trip).
- AST‑sandboxed `content-extra.py` per slide for custom shapes.
- Vision validation via Copilot CLI + LibreOffice export.
- ~4,700 LOC, 300+ tests, OpenSSF Best Practices badge, active maintenance.
- Marked "experimental" — pin to a specific commit SHA.

### 6.2 Why this beats the alternatives (full table in research doc §7)

| Option | Verdict |
|---|---|
| **Microsoft Agent 365 / Work IQ MCP catalog** | No PowerPoint server exists (only Word). |
| **Microsoft Graph PowerPoint API** | Bytes only; no content API. Confirmed on MS Q&A. |
| **Office.js add-in / Office Scripts** | Office Scripts is Excel-only; Office.js requires running PowerPoint UI. |
| **`Ayushmaniar/powerpoint-mcp`** (PyPI `powerpoint-mcp`) | Excellent quality, MIT, but **Windows-only via `pywin32` COM**. Not portable to our skill. UCSD grad student, not Microsoft (skillsmp.com labelling was misleading). |
| **`GongRzhe/Office-PowerPoint-MCP-Server`** | Cross-platform (`python-pptx`), MIT, 32 tools, but shallower than hve-core (no template-aware rebuild, no extraction, no vision QA). |
| **Anthropic `pptx` skill** | License forbids vendoring even in private repos. Off-limits. |
| **Stay with our own `pptx_render.py` but switch to placeholder-binding** | Smaller change, no new dependency, but loses partial-rebuild + extraction + vision QA features. Fallback if hve-core integration proves too costly. |

### 6.3 Concrete integration plan — ✅ COMPLETE

1. ✅ **Vendor.** `skills/pptx-render/` is a verbatim copy of
   `microsoft/hve-core/.github/skills/experimental/powerpoint/` pinned at
   commit `29a2df1b720ddaedd1e328c0c119550bfff52a86`. `NOTICE` records
   provenance + a one-line bug fix to `build_deck.py` (placeholder
   lookup) that should be PR'd upstream. Their `LICENSE` is preserved as
   `LICENSE-microsoft`.
2. ✅ **Adapter.** `src/presentation_forge/render_adapter.py` reads our
   model and writes hve-core's `content/slide-NNN/content.yaml` +
   `content/global/style.yaml`. `materialize_workspace(pres,
   workdir=…, mode="draft"|"final")` returns the paths the subprocess
   needs.
3. ✅ **Shell out.** `builder._render_one()` now calls
   `uv --directory ../pptx-render run python scripts/build_deck.py`.
4. ✅ **Schema.** `theme.yaml` accepts `template:`, `layouts:`,
   `metadata:`, and `defaults:` (see `Theme.from_dict` and the
   example-talk `theme.yaml` for the full format).
5. **Incremental rebuild.** Not yet wired (the SHA-pinned upstream
   supports `--source/--slides` but our builder still does full rebuilds).
   Deferred — current full rebuilds are fast enough for example-talk.
6. ✅ **Delete.** `src/presentation_forge/pptx_render.py` removed.
7. **Vision QA.** Not wired (deferred; needs Copilot CLI installation).
8. ✅ **Test.** End-to-end test suite at
   `skills/presentation-forge/tests/`:
   - `test_template_utils.py` — `.potx`↔`.pptx` normalization (incl. round-trip with the real Microsoft template).
   - `test_slides_parser.py` — parsing + validation incl. `extra_elements:`.
   - `test_spec_theme.py` — `Theme` schema validation.
   - `test_render_adapter.py` — per-layout `slide_to_content` shape, `materialize_workspace` draft/final fan-out.
   - `test_builder_integration.py` — full build → real `.pptx` opened with python-pptx, asserts each slide's `slide_layout.name` matches the configured Microsoft template layout and placeholder text is populated correctly.
   - 57 tests, runs in ~12 s. Run with `uv run pytest`.

### 6.3.1 Two-layer authoring (decided in §3 and re-confirmed)

The codebase keeps **two abstraction layers**:

* `slides.md` — editorial. 10-layout enum, `image_ref`, `notes`,
  agent-friendly. Stable contract for users and authors.
* hve-core's `content/slide-NNN/content.yaml` — compositional.
  Per-slide placeholder indices, inch coords, picture/text elements.
  Generated, never hand-edited.

Translation is one-way and pure (no I/O outside read-the-spec /
write-the-tree). The escape hatch for one-off shapes that the editorial
layer can't express is the per-slide `extra_elements:` list — values are
spliced verbatim into the rendered `elements:` array. See
`references/SLIDES_FORMAT.md` for the documented schema.

### 6.4 Risks / open questions

- hve-core's API is not contract-stable ("experimental"). Mitigation: pin
  commit SHA; treat upgrades as deliberate.
- hve-core uses **per-slide-folder** layout (`content/slide-NNN/`), we use
  **single `slides.md`**. Resolution: keep `slides.md` as the authoring
  layer; the adapter transpiles to their format at build time. Users never
  touch the per-slide-folder layout.
- Their schema may require fields ours doesn't have (e.g. explicit
  `placeholder_idx`). Adapter fills sensible defaults from our `layout:` enum.

---

## 7. Suggested next-session todos (in order)

1. **Resume context.** Read `docs/research/powerpoint-tooling-options.md`
   §3 (hve-core deep dive) and §8 (integration plan).
2. **Pin commit.** Find latest `microsoft/hve-core` commit SHA and record
   it. Verify the path `.github/skills/experimental/powerpoint/` still
   exists at that SHA.
3. **Vendor.** Copy that subtree into `skills/pptx-render/`, preserving
   structure and copyright. Add `NOTICE` file.
4. **Adapter spike.** Write `render_adapter.py` for the simplest layout
   (`title`) only. Verify end-to-end on `example-talk` slide 1 with a
   downloaded Microsoft Office template.
5. **Iterate layouts.** Add adapter mappings for all 6 layouts the
   example-talk uses; verify `forge build --skip-images` still produces
   openable `draft.pptx` + `final.pptx`.
6. **Wire incremental rebuild.** Use `state.json` to compute changed
   slide-ids; pass to hve-core's `--source --slides` mode.
7. **Delete legacy.** Remove `src/presentation_forge/pptx_render.py`.
8. **End-to-end test.** Run full image generation + render with a real
   corporate template. Open in PowerPoint. Verify masters/colors inherit.
9. **Tag.** `gh skill publish --tag v0.1.0` once user approves.

---

## 8. How to invoke things (cheatsheet)

```pwsh
# Validate spec
uv --directory C:\git\presentation-forge\skills\presentation-forge `
   run forge validate --folder C:\git\presentation-forge\skills\presentation-forge\assets\examples\example-talk

# Build (skip image generation, useful for renderer iteration)
uv --directory C:\git\presentation-forge\skills\presentation-forge `
   run forge build --folder <abs-path> --skip-images

# Full build (calls image-generator subprocess)
uv --directory C:\git\presentation-forge\skills\presentation-forge `
   run forge build --folder <abs-path>

# Skill publish dry-run (from repo root)
cd C:\git\presentation-forge
gh skill publish --dry-run
```

**Image-generator `.env`** lives in `skills/image-generator/.env` (gitignored).
Required keys: `AZURE_AI_FOUNDRY_ENDPOINT`. Auth is Entra (DefaultAzureCredential).

---

## 9. Files the next session should read first

1. `docs/plan.md` (this file)
2. `docs/research/powerpoint-tooling-options.md` (the why)
3. `skills/presentation-forge/SKILL.md` (the skill contract)
4. `skills/presentation-forge/src/presentation_forge/builder.py` (orchestration)
5. `skills/presentation-forge/src/presentation_forge/pptx_render.py` (will be replaced)
6. `skills/presentation-forge/assets/examples/example-talk/` (reference deck)
