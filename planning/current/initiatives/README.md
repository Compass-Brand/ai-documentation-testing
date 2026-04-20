# Initiative Workstreams

`initiatives/` is used only when the current repo is operating in `workspace` or `orchestration` scope.

Each active initiative gets its own folder:

- `initiatives/<initiative-id>/phase.md`
- `initiatives/<initiative-id>/phase-state.yaml`

Use these folders to coordinate concurrent repo-targeted workstreams without collapsing multiple active initiatives into one file.

`initiative-index.yaml` remains the machine-readable index for:

- active initiatives
- blocked initiatives
- overlap gates
- integration gates
- routing status across repo targets
