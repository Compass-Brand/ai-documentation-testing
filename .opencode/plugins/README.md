# OpenCode Plugins

`.opencode/plugins/` contains Compass OpenCode plugins.

Rules:

- Each plugin lives in its own folder under `.opencode/plugins/`.
- Implementation metadata and documentation stay with the plugin folder.
- OpenCode command/agent wrappers live in `.opencode/commands/` and `.opencode/agents/`.

Structure:

```text
.opencode/plugins/
  compass-beads.ts
  compass-handoff.ts
  compass-type-inject.ts
  compass-worktree.ts
  compass-bmad/
    README.md
    plugin.yaml
    commands/
    providers/
    tests/
```

If a plugin should auto-load, add a top-level JS/TS entry shim in `.opencode/plugins/` and keep the implementation assets in a matching folder beside it.

If a local plugin imports external packages, declare them in `.opencode/package.json` so OpenCode's Bun install runs on startup.
