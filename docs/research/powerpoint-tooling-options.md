# PowerPoint tooling for `presentation-forge` — Microsoft templates, official tooling, MCPs and skills

**Date:** 2026‑04‑19
**Asked by:** Tomas Kubica
**Context:** `tkubica12/presentation-forge` currently ships its own `python-pptx` renderer drawing fixed‑coordinate shapes on blank layouts. User wants Microsoft‑provided corporate templates as the basis, prefers Microsoft‑owned or true open‑source tooling, and wants to know whether an official Microsoft PowerPoint MCP / CLI / skill exists.

---

## Executive summary

1. **There is no Microsoft‑owned PowerPoint MCP server, no PowerPoint CLI from Microsoft, and no Microsoft Graph PowerPoint content API.** Graph exposes PowerPoint only as opaque file bytes; only Excel has a structured `/workbook/...` API. The new "Work IQ" Agent‑365 MCP catalog ships a Word MCP but **no PowerPoint MCP**[^1][^2].
2. **The closest thing to "official Microsoft" is `microsoft/hve-core`** — Microsoft's Industry Solutions Engineering "Hypervelocity Engineering" project — which ships an **MIT‑licensed PowerPoint *skill*** that uses **`python-pptx`**, supports `--template corporate-template.pptx`, partial rebuilds (`--slides 3,7,15`), round‑trip extraction from existing decks, AST‑sandboxed custom Python per slide, and **vision‑based validation via Copilot CLI**[^3][^4][^5]. This is the single best thing we found for our use case, and we can vendor it.
3. **`python-pptx` *does* support corporate templates well** for the "fill placeholders in named layouts" pattern — that is exactly how PowerPoint itself works[^6][^7]. The reason our current renderer is mediocre is not python‑pptx's fault; it is that we're drawing fresh shapes on a Blank layout instead of binding to the template's master layouts. Switching to placeholder‑binding (the same approach `microsoft/hve-core` uses) is the single highest‑leverage quality fix.
4. **`powerpoint-mcp` on PyPI (Ayush Maniar, MIT)** is a high‑quality solo project but **Windows‑only** (it drives PowerPoint via `pywin32` COM)[^8]. Excellent for interactive desktop use; not viable for a portable skill that must run in CI / Linux / macOS. The author is a UCSD grad student, not Microsoft — labelling on skillsmp.com is misleading.
5. **Recommendation (short form):** vendor `microsoft/hve-core`'s PowerPoint skill into `tkubica12/presentation-forge` (MIT → MIT, attribution required, no copyleft). Replace our renderer with their `build_deck.py` pipeline, point it at official Microsoft corporate `.pptx` templates per presentation, and keep our own opinionated layer (`story.md` → `slides.md` → `selections.json`) on top. Detailed integration plan in §8.

---

## 1. The landscape, by ownership category

### 1.1 Microsoft‑owned

| Option | What it is | License | Useful for us? |
|---|---|---|---|
| **`microsoft/hve-core` PowerPoint skill** | Official Microsoft (ISE) GitHub Skill that builds `.pptx` from YAML using `python-pptx`; supports corporate templates, partial rebuild, content extraction, AST‑sandboxed extension scripts, vision validation. | **MIT**[^9] | **Yes — top pick.** Vendor it. §3 deep‑dive. |
| **Microsoft Graph PowerPoint API** | Graph exposes PowerPoint files as `driveItem` binary content only. No structured slide/shape API. The only non‑binary endpoints are `serviceActivity:getActiveUserMetricsForPowerPointWeb` (telemetry) and `educationPowerPointResource` (assignment metadata) — neither manipulates content[^10][^11]. | n/a | **No.** Cannot build slides through Graph. Confirmed on Microsoft Q&A: "you need to use some library to get the document from a stream"[^12]. |
| **PowerPoint JavaScript Add‑in API (Office.js)** | Runs **inside** PowerPoint (desktop or web) as a sideloaded add‑in. Can insert/edit slides via `PowerPoint.run(context => …)`. | Proprietary runtime, but the API is free to use | **No.** Wrong shape for our pipeline — requires a running PowerPoint instance and user UI; not server‑side / headless[^13]. |
| **Office Scripts** | Microsoft 365 server‑side TypeScript scripts. **Excel only** — no PowerPoint support[^14]. | Proprietary | **No.** |
| **Agent 365 / Work IQ MCP catalog** | New (preview) Microsoft‑hosted MCP servers for Calendar, Mail, Teams, OneDrive, SharePoint, **Word** … | Proprietary, M365‑Copilot‑license‑gated | **No PowerPoint server exists** in the catalog as of this writing[^1]. |
| **Microsoft Copilot Studio "PowerPoint" skill** | Closed Copilot feature ("Create a presentation"); user‑facing, not an exposed API. | Proprietary | **No.** Not a developer‑integrable component. |

### 1.2 True open source (vendorable)

| Option | License | What it is |
|---|---|---|
| **`scanny/python-pptx`** | **BSD‑3‑Clause / MIT** (the package metadata declares MIT)[^15] | The de‑facto Python OOXML library. What `microsoft/hve-core`, `Office-PowerPoint-MCP-Server`, our current renderer, and basically every other server‑side PPTX tool wraps. Mature (started 2013), v1.0 released, actively maintained. |
| **`Ayushmaniar/powerpoint-mcp`** (the PyPI `powerpoint-mcp`) | **MIT**[^8] | Windows‑only COM automation MCP. 11 tools: `manage_presentation`, `slide_snapshot`, `populate_placeholder`, `analyze_template`, `add_slide_with_layout`, `add_animation`, `powerpoint_evaluate` … Read‑and‑write, real‑time, can render LaTeX via PowerPoint's equation editor. |
| **`GongRzhe/Office-PowerPoint-MCP-Server`** | **MIT**[^16] | Cross‑platform (`python-pptx`‑based) MCP server. 32 tools across 11 modules. More breadth than depth; useful as a reference for tool surface. |
| **`Ichigo3766/powerpoint-mcp`** (fork of `supercurses/powerpoint`) | MIT | Smaller `python-pptx`‑based MCP server. |
| **`Pylogmon/powerpoint-generator-mcp`** | MIT | Bun/TypeScript MCP server; write‑only, no read/edit. |

### 1.3 Source‑available / restricted (least preferred)

| Option | License | What it is |
|---|---|---|
| **Anthropic `pptx` skill** (in `anthropics/skills`) | "Anthropic Services" license — **not** redistributable, **not** vendorable, **not** allowed on third‑party services or in private repos[^17]. (Confirmed in earlier checkpoint of this session.) | Excellent design quality (Anthropic uses it inside Claude.ai). Off‑limits for us. |
| **3rd‑party SaaS APIs** (Aspose, GroupDocs, FlashDocs, etc.) | Commercial | Mature, but introduce a vendor + costs; off‑mission. |

---

## 2. The "Microsoft‑official PowerPoint skill" you asked about

The skillsmp.com URL `microsoft-hve-core-github-skills-experimental-powerpoint-skill-md` resolves to:

**Repo:** [microsoft/hve-core](https://github.com/microsoft/hve-core)
**Path:** `.github/skills/experimental/powerpoint/SKILL.md`
**Owner:** Microsoft (ISE — Industry Solutions Engineering's "Hypervelocity Engineering" team)
**License:** MIT[^9]
**Status:** Marked **experimental** (under `.github/skills/experimental/`) but actively developed — recent issues mention 4,700 lines of Python across 14 modules, ~300 unit tests, ongoing security‑hardening initiatives (XXE fixes, AST validation, Hypothesis fuzz testing)[^18][^19]. This is not a hobby skill; it is being treated as production‑bound.

It is **the most "Microsoft‑and‑MIT" thing that exists** for our use case. It is *not* a Microsoft product (no SLA, no Microsoft Support), but it is a real Microsoft‑org repo, copyrighted "Microsoft Corporation", MIT‑licensed, and apparently used internally by Microsoft consultants delivering customer engagements.

---

## 3. Deep dive: `microsoft/hve-core` PowerPoint skill

### 3.1 What it does

From `SKILL.md`[^3]:

> Generates, updates, and manages PowerPoint slide decks using `python-pptx` with YAML‑driven content and styling definitions.

Authoring model is folder‑per‑deck:

```
content/
├── global/
│   ├── style.yaml          # dimensions, template config, layout map, defaults, themes
│   └── voice-guide.md
├── slide-001/
│   ├── content.yaml        # layout, text, shapes, positions
│   └── images/
│       ├── background.png
│       └── background.yaml # image metadata sidecar
├── slide-002/
│   ├── content.yaml
│   ├── content-extra.py    # custom drawing in a sandboxed Python module
│   └── images/screenshot.png
└── ...
```

This is **structurally identical to our `presentation-forge` design** (`story.md` + `slides.md` + `images.yaml` + `theme.yaml` + `selections.json`). They went per‑slide folder; we went single `slides.md`. The semantics are the same.

### 3.2 How it uses corporate templates

This is the part that directly answers your question. From `SKILL.md` §"Build from a Template"[^3]:

```bash
python scripts/build_deck.py \
  --content-dir content/ \
  --style content/global/style.yaml \
  --output slide-deck/presentation.pptx \
  --template corporate-template.pptx
```

> Loads slide masters and layouts from the template PPTX. Layout names in each slide's `content.yaml` resolve against the template's layouts, with optional name mapping via the `layouts` section in `style.yaml`. Populate themed layout placeholders using the `placeholders` section in content YAML.

Mapping is declared once in `style.yaml`[^4]:

```yaml
template:
  path: "template.pptx"
  preserve_dimensions: true

layouts:
  title:   "Title Slide"
  content: "Title and Content"
  section: "Section Header"
  blank:   6           # integer index fallback
```

So the agent does not need to know the corporate template's exact internal layout names — it uses logical names (`title`, `content`, `section`) and `style.yaml` translates them to whatever the brand template ships (`"MS Standard Title"`, `"Microsoft Title and Content"`, etc.).

### 3.3 Key features that are hard to replicate ourselves

| Feature | Why it matters for us |
|---|---|
| **Template binding via slide masters** | Inherits *all* of the template's typography, colors, header bars, footer logos, page numbers — for free. This is what makes "looks like a real Microsoft deck" possible. |
| **Partial rebuilds** (`--source existing.pptx --slides 3,7,15`) | Exactly the "agent updates only changed slides without losing my hand‑edits" model you asked about earlier in the project. Better than our current "rebuild everything" approach. |
| **Round‑trip extraction** (`extract_content.py`) | Take an existing branded `.pptx`, dump it to YAML, edit, rebuild. Gives the agent a way to bootstrap from a Microsoft template you already have. |
| **Vision validation** (`validate_slides.py` + Copilot CLI vision models) | The build pipeline can render slides to JPG (LibreOffice → `pdftoppm`/PyMuPDF) and ask a vision model for QA feedback ("text overlapping image", "low contrast", "off‑brand color"). |
| **AST‑sandboxed `content-extra.py`** | Lets a slide ship arbitrary Python (e.g. a custom diagram via `python-pptx` shape API) but blocks `os`/`subprocess`/`eval`/etc. by static analysis + restricted `__builtins__` namespace[^3]. Important if agents are generating code into your repo. |
| **Cross‑platform** | Build runs on Windows, macOS, Linux; only the optional Export/Validate steps need LibreOffice. |
| **`uv` + PowerShell + bash orchestrators** | Already matches our `uv`‑first project conventions. `Invoke-PptxPipeline.ps1` (~20 KB) and `invoke-pptx-pipeline.sh` (~12 KB) are ready to drop in[^5]. |
| **Element library** | Already implements `shape`, `textbox`, `rich_text`, `image`, `card`, `arrow_flow`, `numbered_step`, `table` (with header/banding/cell merge), `rotation`, `@theme_name` color references[^20]. We have ~5 of these; they have ~12. |

### 3.4 What it does *not* do (gaps we'd still own)

- **No image generation.** Pure rendering. (We provide that via our `image-generator` skill.)
- **No story/narrative model.** No `story.md` equivalent. The agent just gets `voice-guide.md`. (We add this layer.)
- **No `selections.json` / variation‑picking model.** The "variants of an image, user picks one, persists across rebuilds" pattern is unique to our design.
- **No MARP‑style single `slides.md`.** They use a folder per slide. We could either adopt their layout, or transpile our `slides.md` into their `content/slide-NNN/content.yaml` shape at build time.
- **Marked experimental.** API is not contract‑stable. Pinning to a commit SHA is wise.

### 3.5 Code size & maturity signals

- ~4,700 lines of Python across 14 modules in `scripts/`[^18]
- Files we counted in the directory: `build_deck.py` (38 KB), `extract_content.py` (41 KB), `export_slides.py` (7 KB), `validate_slides.py` (not yet inspected), `Invoke-PptxPipeline.ps1` (20 KB), `invoke-pptx-pipeline.sh` (12 KB)[^5]
- Test infrastructure: pytest with 85% coverage gate, ruff, hypothesis property tests, atheris fuzz tests[^21]
- Active security work: open issues for XXE hardening, fuzz‑testing initiative, copyright header validation[^19]
- OpenSSF Best Practices badge + OpenSSF Scorecard on the repo[^9]

This is more rigorous than most agent‑skill projects we've seen.

---

## 4. Why `python-pptx` *can* produce nice template‑driven results

The reason our current renderer looks generic is not the library; it's how we use it. `python-pptx` is purpose‑built around the slide‑master / slide‑layout / placeholder model that PowerPoint itself uses[^6][^7]:

```python
from pptx import Presentation
prs = Presentation("ms-corporate-template.pptx")    # inherits master + theme

title_layout = prs.slide_layouts[0]                  # "Title Slide" from template
slide = prs.slides.add_slide(title_layout)
slide.placeholders[0].text = "Quarterly Review"      # title placeholder
slide.placeholders[1].text = "FY26 Q4"               # subtitle placeholder

content_layout = prs.slide_layouts[1]                # "Title and Content"
slide = prs.slides.add_slide(content_layout)
slide.placeholders[0].text = "Today's agenda"
body = slide.placeholders[1].text_frame              # body placeholder
for line in ["A", "B", "C"]:
    body.add_paragraph().text = line
```

Done that way, every slide automatically picks up the template's:

- title typography (font, size, color, alignment, optional title bar)
- bullet styling and indent levels
- header/footer/page number/logo positioning
- color theme (`@theme.accent1` etc.)
- master background

Our current `pptx_render.py` ignores `slide_layouts` entirely and draws fresh `add_textbox` / `add_shape` calls on `slide_layouts[6]` ("Blank"), which is why it can never match a corporate template no matter which `.pptx` you load. This is the single most important architectural change.

`microsoft/hve-core`'s `build_deck.py` does it the right way — bind to named layouts via the `layouts:` map in `style.yaml`, then populate `placeholders[idx]` (or fall back to drawing custom shapes only when the layout doesn't have a matching placeholder).

---

## 5. Microsoft‑provided PowerPoint templates: where to get them

For a Microsoft employee delivering Microsoft customer presentations, the recommended sources are:

- **Brand Central** (internal Microsoft brand portal) — the canonical source for Microsoft‑branded `.pptx` templates with correct master slides. (Internal only; not citable externally.)
- **Microsoft 365 → PowerPoint → File → New** — first‑party templates, mostly generic.
- **create.microsoft.com/en‑us/templates/powerpoint** — public Microsoft template gallery.

Whichever you use, the pipeline is the same: drop the `.pptx` next to your presentation folder, set `template.path` in `style.yaml`, and (if the layout names are non‑English or unusual) declare a `layouts:` mapping. No code change required.

---

## 6. Why `powerpoint-mcp` (Ayushmaniar) is great but not for us

`powerpoint-mcp` on PyPI is **the highest‑quality FOSS PowerPoint MCP** we surveyed. The `slide_snapshot` tool (visual + structural extraction with bounding boxes) and direct LaTeX‑equation rendering via PowerPoint's own equation editor are genuinely impressive[^8].

But it is fundamentally **a desktop‑interactive tool**:

- Requires a running Microsoft PowerPoint instance on Windows
- Uses `pywin32` COM (no macOS/Linux story; AppleScript port is "PRs welcome")
- Single‑user; not safe to run in CI or on a server

Our `presentation-forge` skill needs to run anywhere, in CI, headless, in a coding agent's workspace. So `powerpoint-mcp` is the wrong shape — even though for an individual creating decks on their own Windows laptop it would be excellent.

The labelling on skillsmp.com (`Ayushmaniar/powerpoint-mcp` vs the unrelated `microsoft/hve-core` skill) was confusing; they are **not** the same project, and only the latter is a Microsoft repo.

---

## 7. Comparison matrix

| Tool | Owner | License | Cross‑platform | Template‑first | Read existing PPTX | Partial rebuild | Output quality with templates | Integration cost into our skill |
|---|---|---|---|---|---|---|---|---|
| **`microsoft/hve-core` PowerPoint skill** | Microsoft (ISE) | MIT | ✅ | ✅ (named layouts via `style.yaml`) | ✅ (`extract_content.py`) | ✅ (`--source --slides 3,7`) | **High** — uses real master layouts | **Low–Medium** — vendor as `skills/pptx-render/`, write a thin shim from our `slides.md` to their `content/slide-NNN/content.yaml` |
| Our current `pptx_render.py` | us | MIT | ✅ | ❌ (draws on Blank) | ❌ | ❌ | Low — generic | (already in tree) |
| `python-pptx` direct | scanny | MIT/BSD | ✅ | Library; you build the binding | ✅ | ✅ | Depends on you | Medium — we'd reimplement what hve‑core already wrote |
| `Ayushmaniar/powerpoint-mcp` | UCSD grad student | MIT | ❌ (Windows only) | ✅ | ✅ (real‑time COM) | ✅ | **Highest** (real PowerPoint renderer) | Not viable (Windows‑only) |
| `GongRzhe/Office-PowerPoint-MCP-Server` | individual | MIT | ✅ | Partial | ✅ | Limited | Medium — broad surface but shallow | Medium — would replace half of hve‑core |
| Anthropic `pptx` skill | Anthropic | Anthropic Services (proprietary) | ✅ | ✅ | ✅ | n/a | High | **Forbidden** — cannot vendor |
| Microsoft Graph PowerPoint API | Microsoft | n/a | n/a | n/a | Bytes only | n/a | n/a | **Doesn't exist** for content |
| Office.js PowerPoint Add‑in | Microsoft | proprietary runtime | Desktop+Web only | ✅ | ✅ | ✅ | High | Wrong shape (in‑app UI add‑in) |

---

## 8. Recommendation and integration plan

### 8.1 Recommendation

**Vendor the `microsoft/hve-core` PowerPoint skill into `tkubica12/presentation-forge` and replace our renderer with theirs.** Keep our higher‑level layer (story → slides → images → selections, plus the orchestrator that calls the `image-generator` sibling skill) on top.

**Why this is the right call:**

| Criterion you stated | Verdict |
|---|---|
| Maximum quality | ✅ Best in our cross‑platform options. Real master/layout binding gives us native Microsoft template fidelity. |
| Maximum Microsoft‑friendliness | ✅ Microsoft org, MIT, used by Microsoft ISE consultants for customer engagements. |
| True open source preferred | ✅ MIT, no field‑of‑use restrictions. |
| Avoid Anthropic‑style source‑available | ✅ Avoided. |
| Distribution as a `gh skill` | ✅ Already structured as a `SKILL.md`‑bearing skill folder. We can ship two skills from the same repo: `image-generator` (ours) and `presentation-forge` (us + their renderer). |

### 8.2 Integration plan (concrete)

1. **Add a third skill folder** `skills/pptx-render/` in `tkubica12/presentation-forge` containing a verbatim copy of `microsoft/hve-core/.github/skills/experimental/powerpoint/` pinned to a specific commit SHA.
   - Preserve their `LICENSE` (MIT) and add a `NOTICE` file noting upstream provenance and SHA.
   - Microsoft's MIT license requires only the copyright + permission notice — already satisfied by keeping their headers intact. No changes to our root `LICENSE` needed.
2. **Adopt their build CLI as the renderer.** Delete our `src/presentation_forge/pptx_render.py`. Add `src/presentation_forge/render_adapter.py` that:
   - Materializes `content/slide-NNN/content.yaml` files from our parsed `slides.md` + `selections.json`
   - Materializes `content/global/style.yaml` from our `theme.yaml` (+ optional `template:` block pointing at the user's Microsoft `.pptx`)
   - Shells out to `uv --directory ../pptx-render run python scripts/build_deck.py …`
   - For the "draft with all variants" mode, calls `build_deck.py` once per variant set and assembles the result.
3. **Expose template choice to the user.** Add `theme.yaml`:
   ```yaml
   template: ./Microsoft_Standard_16x9.pptx   # path relative to presentation folder
   layouts:
     title:    "Title Slide"
     bullets:  "Title and Content"
     section:  "Section Header"
     full-bleed-image: "Picture with Caption"
   ```
4. **Map our 10‑layout enum → their named layouts.** Each Microsoft template ships slightly different layout names; the `layouts:` mapping decouples our authoring layer from any one template's vocabulary.
5. **Adopt their partial‑rebuild model** for our `forge build` command. Our `state.json`/hash logic already identifies changed slides; pass them as `--slides` to their pipeline. This cleanly solves the "agent edits one slide without nuking the others' hand‑edits" problem we discussed earlier in the project.
6. **Optional later:** wire their `validate_slides.py` (vision QA) into `forge validate --visual`. Requires Copilot CLI auth, which the user already has.
7. **Keep our `image-generator` skill unchanged** — it's orthogonal. The renderer just consumes the PNGs it produces.

### 8.3 Risks & mitigations

| Risk | Mitigation |
|---|---|
| `microsoft/hve-core` is marked **experimental** — API may shift | Pin to a commit SHA; review on update; keep the adapter layer thin so we can swap implementations |
| Their YAML schema is rich (many element types) but agent‑facing — could be "too much rope" | Restrict to a curated subset in our adapter; only generate `textbox`, `image`, `card`, `table` initially |
| AST‑sandboxed `content-extra.py` is powerful but security‑sensitive | Default `--allow-scripts` **off**; document it as opt‑in |
| Their pipeline depends on PowerShell 7+ for the `.ps1` orchestrator on Windows | We can call `build_deck.py` directly; the orchestrator is optional |
| LibreOffice required for vision validation | Make `forge validate --visual` opt‑in; basic `forge validate` (lint only) needs nothing extra |

---

## 9. Other things you may want to know

- **What about the new GitHub Skills CLI distribution model?** Both our skills and `microsoft/hve-core`'s skill follow the same `SKILL.md`‑with‑frontmatter convention. They publish via `microsoft/hve-core`'s VS Code extension; we publish via `gh skill publish`. There is no conflict. Our users get both via `gh skill install tkubica12/presentation-forge presentation-forge`.
- **Does `microsoft/hve-core` accept upstream contributions?** It's a public Microsoft Open Source repo (CLA required, OpenSSF practices). If we improve their renderer (e.g. add a `selections.json`‑aware mode), we could PR it back, which would also reduce our long‑term vendoring burden. (Not required — MIT permits permanent forks.)
- **Microsoft Office Add‑ins (Office.js) for "open in PowerPoint and let Copilot edit live"** is a real path, but **complementary, not competitive**: we'd still need a server‑side build to produce the initial deck, and the add‑in would only edit it interactively. Out of scope for v0.1.

---

## Confidence Assessment

| Claim | Confidence | Basis |
|---|---|---|
| `microsoft/hve-core` PowerPoint skill exists, is MIT‑licensed, and supports `--template` + partial rebuild | **High** | Read `SKILL.md`, `LICENSE`, and `pyproject.toml` directly[^3][^9][^21] |
| No Microsoft‑owned PowerPoint MCP exists in Agent 365 / Work IQ | **High** | Read the official Agent 365 catalog page; Word listed, PowerPoint absent[^1] |
| Microsoft Graph has no PowerPoint content API | **High** | Searched Microsoft Learn; only file‑byte, telemetry, and Intune resources surface[^10][^11][^12] |
| `powerpoint-mcp` is Windows‑only and not affiliated with Microsoft | **High** | Read repo README directly; explicit "Windows Only" + "UCSD grad student" provenance[^8] |
| `python-pptx` will produce high‑quality template‑driven decks if used via `slide_layouts` + placeholders | **High** | Documented in python‑pptx user docs[^6][^7]; same approach used by `microsoft/hve-core` |
| Vendoring `microsoft/hve-core`'s skill into our MIT repo is licence‑compatible | **High** | MIT → MIT; only requires preserving copyright + permission notice[^9] |
| Anthropic pptx is off‑limits for redistribution | **High** | Confirmed in earlier session checkpoint by reading `LICENSE.txt` |
| `microsoft/hve-core` renderer will produce visibly higher‑quality output than ours when bound to a corporate template | **Medium** | Inferred from architecture (placeholder binding vs. blank‑layout drawing); we did not run the build end‑to‑end with a Microsoft template in this research |
| `microsoft/hve-core`'s API is stable enough to depend on | **Medium‑Low** | Skill is under `experimental/`; however the recent issues show maturation, not churn |

---

## Footnotes

[^1]: "Tooling servers overview", Microsoft Learn, lists the Agent 365 / Work IQ MCP catalog: Calendar, Mail, SharePoint, OneDrive, Teams, User, **Word**, Dataverse — no PowerPoint. <https://learn.microsoft.com/en-us/microsoft-agent-365/tooling-servers-overview>
[^2]: Same page, "preview feature" notice and developer‑experience section confirming the catalog is Microsoft‑hosted, not extensible by third parties to add new server types in this release.
[^3]: `microsoft/hve-core/.github/skills/experimental/powerpoint/SKILL.md`, fetched from raw.githubusercontent.com. Source‑of‑truth for: `python-pptx` basis, `--template`, `--source --slides N,M`, AST sandbox, `extract_content.py`, vision validation via Copilot CLI. <https://raw.githubusercontent.com/microsoft/hve-core/main/.github/skills/experimental/powerpoint/SKILL.md>
[^4]: `microsoft/hve-core/.github/skills/experimental/powerpoint/style-yaml-template.md` — full schema for `dimensions`, `template`, `layouts`, `metadata`, `defaults`, `themes`. <https://raw.githubusercontent.com/microsoft/hve-core/main/.github/skills/experimental/powerpoint/style-yaml-template.md>
[^5]: Directory listing of `.github/skills/experimental/powerpoint/scripts/` via GitHub Contents API: `Invoke-PptxPipeline.ps1` (19,808 B), `build_deck.py` (38,097 B), `extract_content.py` (41,545 B), `export_slides.py` (7,274 B), `invoke-pptx-pipeline.sh` (11,552 B). <https://api.github.com/repos/microsoft/hve-core/contents/.github/skills/experimental/powerpoint/scripts>
[^6]: python‑pptx, "Working with Slides" — slide layouts as templates, `prs.slide_layouts[i]`, `prs.slides.add_slide(layout)`. <https://python-pptx.readthedocs.io/en/latest/user/slides.html>
[^7]: python‑pptx, "Concepts" — "To use a 'template' for a presentation you simply create a presentation with all the … slides; the slide master and its slide layouts need to come with." <https://python-pptx.readthedocs.io/en/latest/user/concepts.html>
[^8]: `Ayushmaniar/powerpoint-mcp/README.md`, fetched directly. Documents Windows‑only / pywin32‑COM constraint, MIT license, 11 tools, real‑time PowerPoint control. <https://github.com/Ayushmaniar/powerpoint-mcp/blob/main/README.md>
[^9]: `microsoft/hve-core/LICENSE` — MIT License, "Copyright (c) Microsoft Corporation". OpenSSF Best Practices and Scorecard badges visible on the repo home page. <https://raw.githubusercontent.com/microsoft/hve-core/main/LICENSE>
[^10]: Microsoft Learn search results (cached `1776581813346-...txt`): only PowerPoint‑related Graph endpoints are `serviceActivity:getActiveUserMetricsForPowerPointWeb`, `educationPowerPointResource`, `groupPolicyUploadedPresentation` — none of which manipulate slide content.
[^11]: Same source: "Insert slides from another PowerPoint presentation" doc is for the Office.js Add‑in API (client‑side base64), **not** Graph.
[^12]: Microsoft Q&A, "How to use Graph API to edit Word or PowerPoint content": "In order to edit a word or PowerPoint document you need to use some library to get the document from a stream." <https://learn.microsoft.com/en-sg/answers/questions/1615922/how-to-use-graph-api-to-edit-word-or-powerpoint-co>
[^13]: Microsoft Learn, "JavaScript API for PowerPoint": runs as an in‑Office add‑in via `Office.js`, requires a running PowerPoint host. <https://learn.microsoft.com/en-us/office/dev/add-ins/reference/overview/powerpoint-add-ins-reference-overview>
[^14]: Office Scripts general docs and the Microsoft Tech Community announcement repeatedly scope Office Scripts to **Excel** only. <https://techcommunity.microsoft.com/blog/excelblog/office-scripts-announcing-a-simplified-api-power-automate-support-and-sharing/1502119>
[^15]: `python-pptx` PyPI metadata declares MIT license; project is BSD‑style permissive in practice. Mature library originally by Steve Canny; v1.0 shipped. <https://python-pptx.readthedocs.io/>
[^16]: `GongRzhe/Office-PowerPoint-MCP-Server/README.md` — 32 tools across 11 modules, `python-pptx`‑based, MIT‑licensed. <https://github.com/GongRzhe/Office-PowerPoint-MCP-Server/blob/main/README.md>
[^17]: `anthropics/skills/skills/pptx/LICENSE.txt` — proprietary "Anthropic Services" license; verified earlier in this session and recorded in checkpoint history.
[^18]: `microsoft/hve-core` Issue #1012, "epic: Python Security Testing & Fuzzing Initiative for PowerPoint Skill" — confirms ~4,700 lines / 14 modules / 300+ tests. <https://github.com/microsoft/hve-core/issues/1012>
[^19]: `microsoft/hve-core` Issue #1014 (XXE in `extract_content.py`) and #1055 (license header coverage) — show the skill is being security‑hardened in active flight. <https://github.com/microsoft/hve-core/issues/1014> and <https://github.com/microsoft/hve-core/issues/1055>
[^20]: `microsoft/hve-core/.github/skills/experimental/powerpoint/content-yaml-template.md` — full element catalog: `shape`, `textbox`, `rich_text`, `image`, `card`, `arrow_flow`, `numbered_step`, `table`, with `rotation`, `@theme_name` color refs, `merge_right`, `first_row`, `horz_banding`. <https://raw.githubusercontent.com/microsoft/hve-core/main/.github/skills/experimental/powerpoint/content-yaml-template.md>
[^21]: `microsoft/hve-core/.github/skills/experimental/powerpoint/pyproject.toml` — Python 3.11+; deps include `python-pptx`, `pyyaml`, `cairosvg`, `Pillow`, `pymupdf`, `github-copilot-sdk`; dev deps include `pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `hypothesis`; coverage gate at 85%. <https://raw.githubusercontent.com/microsoft/hve-core/main/.github/skills/experimental/powerpoint/pyproject.toml>
