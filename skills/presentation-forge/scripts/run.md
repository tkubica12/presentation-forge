# Running `forge`

```powershell
# One-time bootstrap (creates .venv inside the skill dir)
uv --directory <skill-dir> sync

# Scaffold a new presentation folder
uv --directory <skill-dir> run forge new (Resolve-Path .) my-talk

# Validate the spec
uv --directory <skill-dir> run forge validate (Resolve-Path .\my-talk)

# Generate images only (cached, restartable)
uv --directory <skill-dir> run forge images (Resolve-Path .\my-talk)

# Build PPTX(s) — default is both draft + final
uv --directory <skill-dir> run forge build (Resolve-Path .\my-talk)
uv --directory <skill-dir> run forge build (Resolve-Path .\my-talk) --draft
uv --directory <skill-dir> run forge build (Resolve-Path .\my-talk) --final

# Update a per-slide selection
uv --directory <skill-dir> run forge select (Resolve-Path .\my-talk) hero gpt-image-1.5 2 0

# Per-slide status table
uv --directory <skill-dir> run forge status (Resolve-Path .\my-talk)
```

**Always pass absolute paths** because `uv --directory` changes the working
directory to the skill folder.

`<skill-dir>` is wherever `gh skill install` placed the skill — typically
`.agents/skills/presentation-forge` (project) or
`~/.copilot/skills/presentation-forge` (user).

## Image generation — peer skill

`forge images` and `forge build` shell out to the sibling `image-generator`
skill's `generate-images` CLI. Both skills must be installed from the same
`presentation-forge` repo so the relative path is predictable. The `forge`
CLI auto-detects the sibling at `<this-skill-dir>/../image-generator/`.

If the sibling isn't found, `forge images` will tell you to install it:

```powershell
gh skill install tkubica12/presentation-forge image-generator
```
