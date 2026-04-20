# Tech Writer Standards Bridge

This file is a compatibility bridge for older prompts that still reference a single standards file.

## Source of Truth

Use these built-in framework sources as authoritative:

1. `{project-root}/docs/human/policies/documentation-governance.md`
2. `{project-root}/docs/human/policies/docs-structure-standard.md`
3. `{project-root}/docs/human/policies/style-standard.md`
4. `{project-root}/docs/human/policies/guides-standard.md`
5. `{project-root}/docs/human/policies/architecture-standard.md`
6. `{project-root}/docs/human/templates/*`

Then apply project-specific overrides from:

- `docs/human/policies/user-overrides.md` (if present)

## Required Runtime Layout

All generated product documentation MUST align to:

- `docs/architecture/`
- `docs/development/`
- `docs/getting-started/`
- `docs/guides/`
- `docs/reference/`

Policy/template control plane lives in:

- `docs/human/policies/`
- `docs/human/templates/`

## Critical Rules

- Never overwrite baseline framework policy files with user overrides.
- Keep internal links relative.
- Keep documentation file names lowercase kebab-case.
- Ensure each docs directory includes `README.md`.
