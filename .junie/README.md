# Junie Bundle

This directory is the source for distributed `.junie/` content for JetBrains AI (Junie).

Included:

- `skills/` (auto-generated at build time from `skill-manifest.csv`)

Notes:

- Mirrors upstream BMAD v6.3.0 Junie platform support (#2142).
- Client skills under `dist/.junie/skills/` are generated from the shared skill manifest during `node tools/build.js`.
- Junie reads skills from `.junie/skills/` at the project root.
