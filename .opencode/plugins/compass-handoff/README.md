# Compass Handoff Plugin

Compass-owned OpenCode wrapper for session handoff and continuation.

Pilot scope:

- generate Compass-aware `/handoff` prompts for fresh sessions
- prefill a new session with an editable handoff draft
- inject referenced repo-local files into the new session as synthetic read-like content
- allow the new session to read only the explicit source session transcript for that handoff

This wrapper keeps handoff in the session-continuity lane. It does not replace `bd`, BMAD artifacts, or general memory tooling.

## Authority Boundary

- `bd` remains the issue and task system of record
- BMAD artifacts remain the planning and delivery system of record
- this plugin only carries session context forward

## Install Through Compass Engine

Source-of-truth files live in `src/opencode/`.

To ship this plugin into a target repo:

1. Run `npm run build`
2. Run `npm run push -- --targets opencode --project <target-repo>`

Compass Engine copies the OpenCode bundle into the target repo's `.opencode/` directory. The plugin installs as:

- `.opencode/plugins/compass-handoff.ts`
- `.opencode/plugins/compass-handoff/`
- `.opencode/package.json`

At OpenCode startup, project-level plugins in `.opencode/plugins/` auto-load. If `.opencode/package.json` exists, OpenCode runs `bun install` for the declared dependencies.

## Support Notes

- transcript reads are restricted to the source session that created the handoff
- synthetic file loading is restricted to repo-local readable text files
- the handoff draft is intentionally editable before the new session starts
