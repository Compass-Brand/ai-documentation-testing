# Project Roadmap Checklist

## Inputs

- [ ] High-level brainstorming reviewed
- [ ] High-level market research reviewed
- [ ] High-level domain research reviewed
- [ ] High-level technical research reviewed
- [ ] High-level strategy artifacts reviewed
- [ ] High-level product brief reviewed
- [ ] `repositories.yaml` reviewed when repo routing is part of the roadmap

## Approval Discipline

- [ ] Proposal written to `{roadmap_proposal_file}` before authoritative state changed
- [ ] Ordering, active phase, and deferred work were explicitly approved
- [ ] Unapproved state was not written into `{roadmap_state_file}`

## Authority Rules

- [ ] `{roadmap_state_file}` updated before `{roadmap_summary_file}`
- [ ] `active_phase_id` matches the approved active slice
- [ ] `phases[]` sequence is complete and ordered
- [ ] execution scope and repo targets are recorded for orchestration phases
- [ ] `roadmap.md` and `roadmap.yaml` agree on active phase and sequence
- [ ] `roadmap.md` mirrors `repo_targets` literally and does not substitute aliases like `self`

## Outputs

- [ ] Roadmap update report written to `{default_output_file}`
- [ ] Proposal, roadmap state, roadmap summary, and report identify the current target repo correctly and do not leak `compass-engine` into downstream output
- [ ] Recommended next step is `/bmad-bmm-phase-sync`
