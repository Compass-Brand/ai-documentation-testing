# Context Budgeting Policy

## Purpose

Keep automation inputs intentionally small so wrappers stay deterministic, cheaper to run, and less likely to drift from the approved artifact contract.

## Core Rules

1. Load the minimum context required for the current checkpoint.
2. Prefer sharded planning artifacts over large omnibus documents.
3. Re-read only the artifacts that changed materially since the last accepted checkpoint.
4. Use machine state to decide what must be reloaded; do not rely on memory.
5. Never load future workflow steps or unrelated phase artifacts “just in case.”

## Global Loading Order

1. Command runtime state
2. Canonical machine state
3. Human brief for the current scope
4. Direct upstream planning artifacts
5. Repo/codebase context only when the current command requires it
6. Prior lessons only when they materially affect the active checkpoint

## Per-Command Context Rules

### `auto-plan`

Load in this order:

1. `auto-plan-state.yaml` if present
2. `phase-state.yaml` if present
3. `roadmap.yaml`
4. `roadmap.md`
5. only the roadmap artifacts relevant to the current slice
6. brownfield repo structure and existing docs/planning artifacts when needed

Do not load the full codebase by default for greenfield work.

### `auto-epic-start`

Load:

- current phase state
- target epic
- architecture docs
- relevant WDS outputs
- previous retrospective if the epic is not the first

Do not load unrelated epics or completed stories unless a dependency requires it.

### `auto-story`

Load:

- current phase state
- target story
- minimum PRD, WDS, architecture, and epic slices that directly constrain the story
- the codebase surfaces touched by the story
- reuse evidence, ADRs, and shared patterns directly relevant to the story

Do not load the whole PRD, whole architecture, or broad repo scans unless the story scope truly requires them.

### `auto-epic-end`

Load:

- target epic
- story statuses for the epic
- review, traceability, and implementation evidence for the epic
- current roadmap and phase state only to the extent needed for carry-over and next-epic preview

Do not reload deep planning history unless an unresolved blocker depends on it.

## Sharding Rules

- Prefer `roadmap/` and `current/` shard folders over monolithic planning docs.
- For architecture, prefer the specific files or subfolders tied to the active slice.
- For WDS, load only the active trigger map, scenario set, conceptual specs, and delivery artifacts.
- For security, load only threat model, security review, and secure-gate evidence when the security lane is active.

## Refresh Triggers

Reload context when:

- an approval is rejected
- a current revision changes
- a stale-output record exists for an artifact you plan to reuse
- a blocking risk is added or updated for the current checkpoint

## Resume Rules

- Use machine state to find the first missing, rejected, or revision-mismatched checkpoint.
- Re-read only the artifacts needed to re-enter that checkpoint safely.
- Do not rerun previously accepted steps unless their derived inputs changed.

## Anti-Patterns

- loading complete research trees for a single story
- loading full roadmap and phase history during story execution
- reading reviewer-facing reports as if they were machine state
- inferring security or WDS work from missing files instead of lane outcomes
