# Phase Closeout Checklist

Use this checklist before moving an active phase into `previous/`.

## Prerequisites

1. `../current/phase-state.yaml` is current and reflects the real phase state.
2. `../current/phase.md` is current and aligned with `phase-state.yaml`.
3. Required phase artifacts exist in the expected lane folders for this slice.
4. Blocking risks are resolved or explicitly accepted.
5. Release-gate and closeout work are complete enough to freeze the phase.
6. Automation runtime and gate artifacts needed for audit or resume history are present in the evidence and gate lanes.
7. In workspace or orchestration scope, `../current/initiative-index.yaml` accurately reflects which initiative workstreams are complete, blocked, or still active.

## Closeout Write Order

1. Confirm final phase slug and completion date.
2. Create target folders:
   - `../previous/<phase-slug>-<YYYY-MM-DD>/`
   - `../lessons/<phase-slug>-<YYYY-MM-DD>/`
3. Update `../current/phase-state.yaml` first:
   - set closeout status
   - record archive targets
   - record final workflow and checkpoint state
4. Update `../current/phase.md` second:
   - finalize closeout notes
   - confirm final scope, deliverables, and decisions
5. Update `../roadmap/roadmap.yaml`:
   - set the closed phase status
   - set `actual_end`
   - set `snapshot_path`
   - set `lessons_path`
   - select the next active phase if one exists
6. Update `../roadmap/roadmap.md` to match approved roadmap state.
7. Move superseded roadmap artifacts into the matching archive lanes:
   - `../roadmap/archive/brainstorming/<YYYY-MM-DD>/`
   - `../roadmap/archive/research/market/<YYYY-MM-DD>/`
   - `../roadmap/archive/research/domain/<YYYY-MM-DD>/`
   - `../roadmap/archive/research/technical/<YYYY-MM-DD>/`
   - `../roadmap/archive/strategy/<YYYY-MM-DD>/`
   - `../roadmap/archive/storytelling/<YYYY-MM-DD>/`
   - `../roadmap/archive/product-brief/<YYYY-MM-DD>/`
8. Move the frozen `../current/` contents into `../previous/<phase-slug>-<YYYY-MM-DD>/`.
9. Record lessons in `../lessons/<phase-slug>-<YYYY-MM-DD>/`.
10. Capture promotion candidates for stable docs with owner, lifecycle state, destination path, and replacement note where needed.
11. Recreate a clean `../current/` scaffold for the next active slice.
12. In workspace or orchestration scope, archive closed initiative workstreams and keep only still-active initiative folders in `../current/initiatives/`.

## Validation Checks

1. `phase-state.yaml` and `phase.md` agree on the closed phase identity.
2. `roadmap.yaml` and `roadmap.md` agree on the next active slice and closed phase status.
3. Closed-phase artifacts exist only in `../previous/<phase-slug>-<YYYY-MM-DD>/`.
4. Lesson output exists and is actionable.
5. `../current/` contains only next-phase starter structure.
6. Promotion candidates are explicitly recorded; unpromoted planning artifacts remain in the phase snapshot.
7. In workspace or orchestration scope, `initiative-index.yaml` matches the remaining initiative folders and their statuses.

## Failure Modes To Avoid

- updating `roadmap.md` without updating `roadmap.yaml`
- updating `phase.md` without updating `phase-state.yaml`
- leaving final artifacts in `current/` after closeout
- archiving roadmap documents without the lane-specific date folders
- skipping lessons extraction
- using non-standard folder names or date formats
- silently promoting planning artifacts into `docs/` without owner and lifecycle metadata
