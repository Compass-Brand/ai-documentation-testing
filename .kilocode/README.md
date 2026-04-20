# KiloCoder Bundle

This directory is the source for distributed `.kilocode/` content.

Included:

- `skills/` (auto-generated at build time from `skill-manifest.csv`)

Notes:

- Mirrors upstream BMAD v6.3.0 KiloCoder platform support (#2151).
- Client skills under `dist/.kilocode/skills/` are generated from the shared skill manifest during `node tools/build.js`.
- KiloCoder reads skills from `.kilocode/skills/` at the project root.
