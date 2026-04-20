# Compass Worktree Plugin

Compass-managed local packaging for `kdcokenny/opencode-worktree`.

Pilot posture:

- keep upstream `worktree_create` and `worktree_delete` behavior intact
- treat this as a workspace utility, not a planning or tracking plugin
- install it through the normal Compass Engine `.opencode/` bundle

## What This Plugin Does

- creates isolated git worktrees for OpenCode sessions
- launches a new terminal with OpenCode inside the worktree
- persists worktree session state in the user home directory
- cleans up worktrees through the plugin lifecycle

## Authority Boundary

- `bd` remains the issue and task system of record
- BMAD artifacts remain the planning and delivery system of record
- this plugin only provides isolated execution surfaces

## Install Through Compass Engine

Source-of-truth files live in `src/opencode/`.

To ship this plugin into a target repo:

1. Run `npm run build`
2. Run `npm run push -- --targets opencode --project <target-repo>`

Compass Engine copies the OpenCode bundle into the target repo's `.opencode/` directory. The plugin installs as:

- `.opencode/plugins/compass-worktree.ts`
- `.opencode/plugins/compass-worktree/`
- `.opencode/package.json`

At OpenCode startup, project-level plugins in `.opencode/plugins/` auto-load. If `.opencode/package.json` exists, OpenCode runs `bun install` for the declared dependencies.

## Downstream Requirements

- `git` with `worktree` support
- Bun-backed OpenCode runtime
- repo-local `.opencode/worktree.jsonc` if the project wants custom sync or hook behavior

## Support Caveats

- upstream supports terminal launch on macOS, Linux, Windows, WSL, `tmux`, and `cmux`
- hook commands still execute with `bash -c`
- Windows repos that want hooks need bash availability such as Git Bash or WSL
