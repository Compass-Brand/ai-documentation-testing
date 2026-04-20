# Compass Beads Plugin

Compass-owned OpenCode wrapper for beads integration.

Pilot scope:

- inject `bd prime` context into primary sessions
- re-inject on compaction
- register a small `bd-*` command set
- register a Compass-aligned beads task agent

This wrapper vendors a small upstream baseline from `joshuadavidthomas/opencode-beads` and narrows it to Compass workflow requirements.

## Install Through Compass Engine

Source-of-truth files live in `src/opencode/`.

To ship this wrapper into a target repo:

1. Run `npm run build`
2. Run `npm run push -- --targets opencode --project <target-repo>`

Compass Engine copies the OpenCode bundle into the target repo's `.opencode/` directory. The wrapper installs as:

- `.opencode/plugins/compass-beads.ts`
- `.opencode/plugins/compass-beads/`
- `.opencode/package.json`

At OpenCode startup, project-level plugins in `.opencode/plugins/` auto-load. If `.opencode/package.json` exists, OpenCode runs `bun install` for the declared dependencies.

## Downstream Requirements

- `bd` must be installed and available on `PATH`
- the target repo must be initialized for beads
- Compass BMAD and beads remain authoritative for task state
