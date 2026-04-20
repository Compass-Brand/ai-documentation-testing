# Compass Type Inject Plugin

Compass-owned OpenCode wrapper for TypeScript-aware code intelligence.

Pilot scope:

- inject relevant external type signatures into TypeScript and Svelte file reads
- expose namespaced type lookup and type-check tools
- append guarded post-write TypeScript diagnostics without blocking writes

This wrapper keeps `type-inject` in the code-intelligence lane. It does not own planning, tracking, or workflow state.

## Authority Boundary

- `bd` remains the issue and task system of record
- BMAD artifacts remain the planning and delivery system of record
- this plugin only improves TypeScript context and diagnostics

## Install Through Compass Engine

Source-of-truth files live in `src/opencode/`.

To ship this plugin into a target repo:

1. Run `npm run build`
2. Run `npm run push -- --targets opencode --project <target-repo>`

Compass Engine copies the OpenCode bundle into the target repo's `.opencode/` directory. The plugin installs as:

- `.opencode/plugins/compass-type-inject.ts`
- `.opencode/plugins/compass-type-inject/`
- `.opencode/package.json`

At OpenCode startup, project-level plugins in `.opencode/plugins/` auto-load. If `.opencode/package.json` exists, OpenCode runs `bun install` for the declared dependencies.

## Downstream Requirements

- Bun-backed OpenCode runtime
- TypeScript files or packages in the repo
- a readable `tsconfig.json` near the files you want to inspect or check

## Support Notes

- TypeScript files are first-class in pilot 1
- Svelte support is best-effort through the upstream core package
- read-time injection and write-time diagnostics soft-fail when type context cannot be resolved
