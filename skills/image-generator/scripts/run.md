# Running the generator

The skill ships a uv project. After `gh skill install` (or copying this
directory anywhere), the workflow is always:

```powershell
# 1. One-time bootstrap (creates .venv inside the skill dir)
uv --directory <skill-dir> sync

# 2. Make sure the user is authenticated and the endpoint is configured
az login
$env:AZURE_FOUNDRY_ENDPOINT = "https://<resource>.services.ai.azure.com"
# or: copy <skill-dir>/assets/env.example to ./.env in the user's project

# 3. Generate (use absolute YAML path + explicit --output-dir, since
#    `uv --directory` changes CWD to the skill folder)
uv --directory <skill-dir> run generate-images `
    (Resolve-Path <path-to-yaml>) --output-dir "$PWD\output"
```

`<skill-dir>` is wherever `gh skill install` placed this skill — typically
`.agents/skills/image-generator` (project scope) or
`~/.copilot/skills/image-generator` (user scope).

Run from the **user's project directory**, not from inside the skill dir, so
that `.env` discovery and `output_dir` defaults land in the right place.

See `references/YAML_SCHEMA.md` for the full YAML schema.
