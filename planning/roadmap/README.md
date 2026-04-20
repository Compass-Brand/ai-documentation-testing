# Project Roadmap

`roadmap/` is the cross-phase planning lane.

## Control Files

- `roadmap.yaml`: machine-readable roadmap state and active-phase selection
- `roadmap.md`: human-readable roadmap summary
- `../repositories.yaml`: machine-readable repo topology used to validate repo targets for orchestration phases

`roadmap.yaml` is authoritative if the two disagree.

## Artifact Lanes

- `brainstorming/`: high-level brainstorming and macro exploration
- `research/market/`: high-level market research
- `research/domain/`: high-level domain research
- `research/technical/`: high-level technical research
- `strategy/`: innovation strategy and opportunity framing
- `storytelling/`: optional high-level storytelling artifacts
- `product-brief/`: high-level product brief artifacts
- `archive/`: superseded roadmap artifacts organized by lane and date

## Update Rules

- only approved roadmap state belongs in `roadmap.yaml` and `roadmap.md`
- draft roadmap changes should live in proposal or automation-report artifacts until approved
- every phase listed in `roadmap.yaml` must appear in `roadmap.md`
- orchestration and workspace phases must reference repo ids that exist in `../repositories.yaml`
- automation proposals such as `auto-plan-roadmap-proposal.md` remain in `current/implementation/evidence/` until approved and must not be treated as roadmap truth
