# Compass BMAD Workflow (Roadmap-Driven Canonical Order)

This document defines the shipped Compass BMAD order aligned to:

- the shipped BMAD runtime in `_bmad/`
- `planning/`
- `planning/templates/`
- `docs/`

Compass should operate as a roadmap-driven BMAD system, not as a one-time MVP pipeline.

Run `A. Project-Level Setup And Direction` at project start or when re-baselining the project.
Then repeat `B. Per-Phase Execution Loop` for each approved roadmap slice.

In a polyrepo workspace, the same BMAD method applies at three altitudes:

- workspace root: portfolio orchestration
- parent repos with child repos: domain or program orchestration
- leaf repos: repo-local delivery

Authoritative ownership always stays at the actual repo root being worked on. Parent and workspace repos coordinate; they do not own child repo-local PRDs, architecture, stories, or implementation evidence.

When shortened paths are used in this file:

- `roadmap/...` means `planning/roadmap/...`
- `current/...` means `planning/current/...`

Some approved steps still do not have a dedicated slash command. Remaining template-driven steps should use the planning framework and templates until a dedicated workflow is implemented.

## Inputs Used For This Ordering

- `_bmad/bmm/module-help.csv`
- `_bmad/core/module-help.csv`
- `_bmad/bmm/**`
- `_bmad/core/**`
- `planning/**`
- `planning/templates/**`
- `docs/**`
- shipped extension workflows already normalized into `_bmad/bmm/`

## Legend

- `Required`: Part of the canonical progression for the full workflow.
- `Optional`: Valid in-order step you can skip without breaking the spine.
- `Conditional`: Run when the lane is activated by project characteristics or explicit choice.
- `Planned / Template-Driven`: Approved workflow step that currently depends on the planning framework, templates, or automation wrappers rather than a dedicated slash command.

## A. Project-Level Setup And Direction

Run this layer once at project start or when the project is being re-baselined.

### 1. Initialization

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Sync Repositories | `/bmad-bmm-sync-repositories` | Conditional | Approved `planning/repositories.yaml` updates when repo topology changed or was incomplete |
| 2 | Workspace Bootstrap | `/bmad-bmm-workspace-bootstrap` | Conditional | Aggregate bootstrap report plus targeted repo initialization status from a workspace or orchestration root |
| 3 | Initialize Docs | `/bmad-bmm-init-docs` | Required | Deployed docs tree in `docs/` plus migration and governance evidence derived from `docs/` |
| 4 | Initialize Planning | `/bmad-bmm-init-planning` | Required | Planning scaffold plus `roadmap.md`, `roadmap.yaml`, `phase.md`, and `phase-state.yaml` baselines |
| 5 | Generate / Seed Project Context | `/bmad-bmm-generate-project-context` | Conditional | Brownfield context now, or greenfield seed context after high-level framing in `current/research/project-context/` |

Notes:

- Brownfield should initialize from live repo reality and generate context early.
- Greenfield should initialize structure first, then generate a seed context after high-level framing, and regenerate richer context later.
- Initialization establishes structure and context. It should not try to complete detailed planning.
- `Sync Repositories` is the topology-maintenance workflow for `planning/repositories.yaml`. Use it whenever repos are added, moved, or missed.
- `Workspace Bootstrap` is the top-level safety-net workflow. It is only for `workspace` or `orchestration` roots and should reuse `Initialize Planning` plus `Initialize Docs` semantics for targeted repos.
- `Initialize Docs` must read standards from `docs/` in `compass-engine`, but its deployed outputs belong in root `docs/`.
- Initialization should also verify `bd` is available, recover issue-tracking context with `bd prime` when needed, and ensure repo work will be tracked in Beads rather than ad hoc TODO lists.

### 2. High-Level Analysis

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | High-Level Brainstorm | `/bmad-brainstorming` | Required | `roadmap/brainstorming/` |
| 2 | High-Level Market Research | `/bmad-bmm-market-research` | Required | `roadmap/research/market/` |
| 3 | High-Level Domain Research | `/bmad-bmm-domain-research` | Required | `roadmap/research/domain/` |
| 4 | High-Level Technical Research | `/bmad-bmm-technical-research` | Required | `roadmap/research/technical/` |
| 5 | High-Level Innovation Strategy | `/bmad-cis-innovation-strategy` | Required | `roadmap/strategy/` |
| 6 | High-Level Opportunity Framing | `/bmad-cis-design-thinking` | Required | `roadmap/strategy/` |
| 7 | High-Level Storytelling | Deferred / Template-Driven storytelling artifact when enabled | Conditional | `roadmap/storytelling/` or fold into the high-level brief when storytelling is embedded |
| 8 | High-Level Product Brief | `/bmad-bmm-create-product-brief` | Required | `roadmap/product-brief/` |

Notes:

- This layer exists to preserve long-horizon thinking beyond the MVP.
- These outputs should remain smaller roadmap artifacts, not one giant strategy document.
- The three research lanes are the first automation candidates.

### 3. Project Roadmap

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Create / Update Roadmap Proposal | `/bmad-bmm-project-roadmap` | Required | `roadmap/roadmap-update-proposal-YYYY-MM-DD.md` |
| 2 | Approve Current, Next, Deferred, and Dependent Slices | Approval checkpoint inside `/bmad-bmm-project-roadmap` | Required | Approved active slice, next slice, deferred work, and dependencies |
| 3 | Write Approved Roadmap Summary And State | `/bmad-bmm-project-roadmap` | Required | `roadmap/roadmap.md`, `roadmap/roadmap.yaml`, and roadmap update report |

Notes:

- `roadmap.md` is the human-readable summary.
- `roadmap.yaml` is the machine-readable roadmap source of truth.
- workspace and orchestration phases must also record execution scope and repo targets.
- This is the persistent cross-phase planning layer that solves BMAD's continuity problem.
- `Project Roadmap` now has a dedicated workflow, but it must still respect the approval rule that only approved state belongs in `roadmap.yaml`.

## B. Per-Phase Execution Loop

Repeat this loop for each approved roadmap slice.

### 4. Phase Sync

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Phase Sync | `/bmad-bmm-phase-sync` | Required | `current/phase.md`, `current/phase-state.yaml`, active-slice scope framing |

Notes:

- `Phase Sync` is the formal roadmap-slice selection and framing workflow.
- Do not create a separate roadmap-selection workflow unless later implementation proves that `Phase Sync` is overloaded.
- `phase-state.yaml` is the machine authority for active-phase state.
- `phase.md` is the human-readable phase brief.
- when execution scope is `workspace` or `orchestration`, `Phase Sync` must also capture repo targets and route the next checkpoint to `Initiative Routing`.
- `Phase Sync` should reconcile the active Beads phase issue and store the issue refs in `phase-state.yaml` before detailed analysis begins.

### 4A. Initiative Routing (Workspace / Orchestration Scope Only)

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Initiative Routing | `/bmad-bmm-initiative-routing` | Conditional | `current/initiative-index.yaml` plus `current/initiatives/<initiative-id>/` |

Notes:

- run this after `Phase Sync` when the active phase execution scope is `workspace` or `orchestration`
- this workflow fans the approved active phase into concurrent repo-targeted initiative workstreams
- it must not create repo-local delivery artifacts in the wrong repo
- every targeted repo still runs its own repo-local `Phase Sync` before detailed analysis begins there

### 5. Detailed Analysis

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Generate / Refresh Project Context | `/bmad-bmm-generate-project-context` | Required | `current/research/project-context/` |
| 2 | Detailed Brainstorm | `/bmad-brainstorming` (phase-scoped run) | Required | `current/brainstorming/detailed/` |
| 3 | Detailed Market Research | `/bmad-bmm-market-research` (phase-scoped run) | Required | `current/research/market/` |
| 4 | Detailed Domain Research | `/bmad-bmm-domain-research` (phase-scoped run) | Required | `current/research/domain/` |
| 5 | Detailed Technical Research | `/bmad-bmm-technical-research` (phase-scoped run) | Required | `current/research/technical/` |
| 6 | Detailed Innovation Strategy | `/bmad-cis-innovation-strategy` (phase-scoped run) | Required | `current/research/strategy/` |
| 7 | Detailed Opportunity Framing | `/bmad-cis-design-thinking` (phase-scoped run) | Required | `current/research/strategy/` |
| 8 | Detailed Product Brief | `/bmad-bmm-create-product-brief` (phase-scoped run) | Required | `current/planning/brief/` |

Notes:

- This layer is focused only on the active roadmap slice.
- Detailed analysis should feed planning and solutioning, not become detached research archives.
- Brownfield should inherit prior lessons and previous-phase constraints, but still refresh assumptions against current repo reality.

### 6. Planning And Experience Design

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Create PRD | `/bmad-bmm-create-prd` | Required | `current/planning/prd/` |
| 2 | Validate PRD | `/bmad-bmm-validate-prd` | Required | `current/planning/prd/` plus gate evidence as needed |
| 3 | Edit PRD | `/bmad-bmm-edit-prd` | Conditional | `current/planning/prd/` |
| 4 | Trigger Mapping | `/bmad-wds-trigger-mapping` | Conditional | `current/planning/ux-design/trigger-mapping/` |
| 5 | Outline Scenarios | `/bmad-wds-outline-scenarios` | Conditional | `current/planning/ux-design/outline-scenarios/` |
| 6 | Create UX Design | `/bmad-bmm-create-ux-design` | Conditional | `current/planning/ux-design/` |
| 7 | Conceptual Specifications | `/bmad-wds-conceptual-specs` | Conditional | `current/planning/ux-design/conceptual-specifications/` |
| 8 | Design Delivery | `/bmad-wds-design-delivery` | Conditional | `current/planning/ux-design/design-delivery/` |
| 9 | Update Docs (Planning) | `/bmad-bmm-update-docs` | Optional | Docs deltas plus evidence of planning artifact updates |

Notes:

- WDS stays after PRD and before architecture.
- If the WDS lane exposes requirement gaps, route back to `Edit PRD` before proceeding to architecture.
- Planning and docs should be updated continuously even if `Update Docs` is not always treated as a formal gate.
- If command implementation still invokes `Phase Sync` at planning entry, treat it as a confirmation checkpoint, not as a second scope-selection workflow.
- Planning-stage docs updates should classify new docs by Diataxis mode and capture promotion evidence when planning artifacts become stable docs.

### 7. Solutioning

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Create Architecture | `/bmad-bmm-create-architecture` | Required | `current/planning/architecture/` |
| 2 | Threat Modeling | `/bmad-cybersec-threat-modeling` | Conditional | `current/planning/architecture/threat-modeling/` |
| 3 | Security Architecture Review | `/bmad-cybersec-security-architecture-review` | Conditional | `current/planning/architecture/security-review/` |
| 4 | Test Design (System-Level mode) | `/bmad-tea-testarch-test-design` | Optional | `current/testing/test-design/` |
| 5 | Create Epics and Stories | `/bmad-bmm-create-epics-and-stories` | Required | `current/planning/epics/` (`epics.md` for the manual flow; automation wrappers may stage draft artifacts separately) |
| 6 | Test Framework Setup | `/bmad-tea-testarch-framework` | Optional | `current/testing/automation/` |
| 7 | CI/CD Alignment | `/bmad-tea-testarch-ci` | Optional | `current/testing/automation/` and `current/implementation/evidence/` |
| 8 | Secure Readiness Gate | `/bmad-cybersec-secure-gates` | Conditional | `current/testing/gates/draft/security/` while pending, then `current/testing/gates/security/readiness/` once accepted |
| 9 | Check Implementation Readiness | `/bmad-bmm-check-implementation-readiness` | Required | `current/testing/gates/draft/` until approved |
| 10 | Update Docs (Solutioning) | `/bmad-bmm-update-docs` | Optional | Docs deltas plus architecture and readiness references |

Notes:

- CYBERSEC runs after an initial architecture draft, not before architecture exists.
- Security remains conditional, not mandatory for every project.
- CI work should align with the repo's real delivery infrastructure rather than blindly scaffolding a new pipeline.
- Automation wrappers may stage draft epics or stories before readiness approval, but the current manual flow writes `epics.md` in `current/planning/epics/` and creates story files only after sprint planning.
- Solutioning-stage docs updates should create or revise ADRs and architecture docs when decisions are expensive to reverse.

### 8. Implementation

Follow this phase from top to bottom for the active approved slice.

#### 8A. Sprint Kickoff

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Sprint Planning | `/bmad-bmm-sprint-planning` | Required | `current/implementation/stories/sprint-status.yaml` plus sprint routing |
| 2 | Sprint Status | `/bmad-bmm-sprint-status` | Optional | `current/implementation/stories/sprint-status.yaml` |

#### 8B. Epic Loop (Repeat for Every Epic)

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Implementation Brainstorming | `/bmad-bmm-implementation-brainstorming` | Optional | `current/brainstorming/detailed/` |
| 2 | Test Design (Epic-Level mode) | `/bmad-tea-testarch-test-design` | Optional | `current/testing/test-design/` |
| 3 | Implementation Research | `/bmad-bmm-implementation-research` | Optional | `current/research/implementation/` |

Notes:

- `Implementation Brainstorming` and `Implementation Research` are best used for epics with delivery risk, unknowns, or multiple approaches.
- `Test Design (Epic-Level mode)` remains the main TEA insertion point before the story loop for each epic.

#### 8C. Story Loop (Repeat for Every Story in Current Epic)

| Run | ID | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- | --- |
| 1 | CS | Create Story | `/bmad-bmm-create-story` | Required | `current/implementation/stories/` |
| 2 | VS | Validate Story | `/bmad-bmm-create-story` (Validate Mode) | Required | Story validation notes in story and evidence lanes |
| 3 | AT | ATDD | `/bmad-tea-testarch-atdd` | Optional | `current/testing/test-design/` |
| 4 | DS | Dev Story | `/bmad-bmm-dev-story` | Required | Repo codebase plus updated story artifact |
| 5 | TA | Test Automation | `/bmad-tea-testarch-automate` | Optional | `current/testing/automation/` |
| 6 | QA | QA Automation Test | `/bmad-bmm-qa-automate` | Optional | `current/testing/automation/` |
| 7 | CR | Code Review | `/bmad-bmm-code-review` | Optional | `current/implementation/evidence/` |
| 8 | RV | Test Review | `/bmad-tea-testarch-test-review` | Optional | `current/testing/reviews/` |
| 9 | TR | Traceability | `/bmad-tea-testarch-trace` | Optional | `current/testing/gates/` |
| 10 | SS | Sprint Status | `/bmad-bmm-sprint-status` | Optional | `current/implementation/stories/sprint-status.yaml` |

Story loop notes:

- Before `DS`, perform a reuse check using `planning/templates/implementation/reuse-check.md` or equivalent automation evidence.
- `TA` is the preferred default post-dev automation lane.
- `QA` is a secondary expansion lane for explicit API/E2E generation or when the project already has strong framework conventions and you want additional coverage beyond the main TEA lane.
- `Code Review` stays before `Test Review`.
- Every active implementation story should have a Beads issue before `DS`; claim it with `bd update <id> --status in_progress`, create follow-up issues for newly discovered work, and close it only after the story is accepted.

Loop routing:

1. `CS` -> `VS` -> `AT` -> reuse check -> `DS`
2. `TA` -> `QA` if needed -> `CR`
3. `RV` -> `TR` -> `SS` as needed
4. If review or gate fails, route back to `DS` and repeat downstream steps.

#### 8D. Epic Wrap-Up (After Stories in Current Epic)

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Update Docs (Implementation) | `/bmad-bmm-update-docs` | Optional | Docs deltas plus implementation evidence |
| 2 | Retrospective | `/bmad-bmm-retrospective` | Optional | `current/implementation/retrospectives/` |
| 3 | Sprint Status | `/bmad-bmm-sprint-status` | Optional | `current/implementation/stories/sprint-status.yaml` |

### 9. Release Gate

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | NFR Assessment | `/bmad-tea-testarch-nfr` | Optional | `current/testing/gates/` |
| 2 | Final Test Review | `/bmad-tea-testarch-test-review` | Optional | `current/testing/reviews/` and release audit evidence |
| 3 | Traceability Gate | `/bmad-tea-testarch-trace` | Optional | `current/testing/gates/` |
| 4 | Secure Release Gate | `/bmad-cybersec-secure-gates` | Conditional | `current/testing/gates/security/release/` |
| 5 | Validate Docs | `/bmad-bmm-validate-docs` | Optional | Docs validation evidence |
| 6 | Sprint Status | `/bmad-bmm-sprint-status` | Optional | Final sprint snapshot in `current/implementation/stories/sprint-status.yaml` |

Notes:

- Release gating should collect evidence rather than rely on intuition.
- Secure release gates should run only when the security lane is active.
- Docs validation should audit structure, governance, lifecycle, Diataxis, architecture requirements, and promotion rules, not just link hygiene.

### 10. Phase Closeout

| Run Order | Workflow | Command / Mechanism | Gate Type | Primary outputs / destination |
| --- | --- | --- | --- | --- |
| 1 | Phase Closeout | `/bmad-bmm-phase-closeout` | Required | `previous/`, `lessons/`, `roadmap/`, and closeout evidence |

Notes:

- `Phase Closeout` archives the active slice, extracts lessons, updates roadmap state, and recreates the next clean `current/` scaffold.
- The closeout write order should be:
  1. update `current/phase-state.yaml`
  2. update `current/phase.md`
  3. update `roadmap/roadmap.yaml`
  4. update `roadmap/roadmap.md`
- Closeout is where continuity is preserved across BMAD cycles.
- Closeout should also reconcile Beads: close the completed phase issue, create carry-over issues for deferred work, and run `bd sync`.

## Greenfield And Brownfield Routing Rules

1. Brownfield should initialize docs and planning from the live repo reality and generate project context early.
2. Greenfield should initialize structure first, complete high-level framing, then generate a seed project context and regenerate richer context later.
3. Detailed analysis still runs for the active slice in both cases.
4. Storytelling may run as a distinct lane, fold into the high-level brief, or stay off depending on `storytelling_mode`.
5. The WDS lane should activate when workflows, user journeys, UX complexity, or behavior design matter.
6. The CYBERSEC lane should activate by heuristic or explicit choice, with extra weight for legacy auth, data flows, inherited attack surface, and regulated work.

## Polyrepo Routing Rules

1. The deployed BMAD structure is the same everywhere: `docs/`, `planning/roadmap/`, `planning/current/`, `planning/previous/`, and `planning/lessons/`.
2. Workspace and parent repos also maintain `planning/repositories.yaml`, `planning/current/initiative-index.yaml`, and `planning/current/initiatives/`.
3. Nested repo roots are authoritative for their own planning and docs state.
4. Workspace and parent repos coordinate child workstreams; they do not own child repo-local delivery artifacts.
5. Multiple concurrent initiatives are allowed in workspace or orchestration scope, but overlap on the same repo, shared interface, or release boundary must be explicitly gated.
6. `repositories.yaml` is authoritative for repo ids, parent-child relationships, and repo-root ownership.
7. `initiative-index.yaml` is authoritative for concurrent initiative routing state in orchestration scope.

## Framework Control Rules (Exact)

1. No project should skip `roadmap.md`, `roadmap.yaml`, `phase.md`, or `phase-state.yaml`.
2. Workspace and parent repos should also maintain `repositories.yaml` and `initiative-index.yaml`.
3. `roadmap.yaml` is authoritative over `roadmap.md`.
4. `phase-state.yaml` is authoritative over `phase.md`.
5. `repositories.yaml` is authoritative for repo routing and ownership.
6. `initiative-index.yaml` is authoritative for concurrent initiative routing in orchestration scope.
7. Project-level work writes to `roadmap/`; active-slice work writes to `current/`.
8. Any remaining template-driven roadmap or phase steps should use `planning/templates/` until dedicated slash commands exist.

## Beads Control Rules (Exact)

1. `bd` is the issue and task system of record for Compass BMAD work.
2. TodoWrite and markdown task lists are not authoritative task trackers for active Compass BMAD delivery.
3. Every active phase should have a Beads phase issue recorded in `phase-state.yaml`.
4. Workspace or orchestration initiatives may also record a parent Beads issue, but child repo delivery work still belongs to child repo-local issues.
5. Every implementation story should have a Beads story issue before `Dev Story` begins.
6. Newly discovered blockers, defects, and carry-over work should be recorded with `bd create`, not only in markdown evidence.
7. Phase and automation closeout should reconcile issue status with `bd close` where appropriate and finish with `bd sync`.

## Documentation Control Rules (Exact)

1. `docs/` is the canonical documentation framework source inside `compass-engine`.
2. Deployed project documentation belongs in root `docs/`, not in `reference/`.
3. Projects using Compass BMAD docs workflows must install the docs control-plane lanes required by the documentation framework:
   - `docs/human/policies/`
   - `docs/human/templates/`
   - `docs/human/policies/user-overrides.md`
   - `docs/ai/README.md`
4. `Update Docs` must classify changed docs by primary Diataxis mode, maintain lifecycle and ownership metadata, and preserve promotion evidence when planning artifacts become canonical docs.
5. `Validate Docs` must enforce documentation-governance, docs-structure, style, guides, and architecture standards together.

## TEA Insertion And Replacement Rules (Exact)

1. TEA does not replace required framework control artifacts or required BMM progression gates.
2. `test-review` does not replace `code-review`.
3. `testarch-automate` is the preferred default post-dev automation lane; `bmm-qa-automate` is a secondary expansion lane.
4. `nfr-assess` does not replace traceability gate decisions; it complements gate evidence.
5. `test-design` appears twice by design:
   - Solutioning: system-level mode
   - Implementation: epic-level mode
6. The security lane does not replace `create-architecture` or `check-implementation-readiness`; it adds conditional risk and gate checks around them.
7. `bmad-cybersec-secure-gates` appears twice by design:
   - Solutioning: secure readiness gate
   - Release Gate: secure release gate

## Compass Extension Rules (Exact)

1. High-level analysis is a permanent project-level lane, not a one-time ideation dump.
2. The project roadmap is a first-class BMAD control surface, not optional admin work.
3. `Phase Sync` is the roadmap-slice selector and framing workflow.
4. `Initiative Routing` is the orchestration-only bridge from a workspace or parent-repo phase into concurrent targeted repo workstreams.
5. `Innovation Strategy` and `Opportunity Framing` enrich analysis and feed the brief; they do not replace the brief.
6. `Problem Solving` remains an anytime lane and should not be forced into every default run.
7. `Trigger Mapping`, `Outline Scenarios`, `Conceptual Specifications`, and `Design Delivery` do not replace `Create PRD` or `Create UX Design`; they deepen the handoff lane between planning and solutioning.
8. If the WDS lane exposes requirement gaps, route back to `Edit PRD` before architecture.
9. `Threat Modeling` and `Security Architecture Review` should run after an initial architecture draft, not before architecture exists.
10. `Secure Readiness Gate` and `Secure Release Gate` are conditional gates, not default gates for every project.
11. Before `Dev Story`, check for reuse of existing components, services, queries, patterns, and data access paths before approving net-new code.

## Required Progression Chain (Framework + BMM Quick Scan)

1. Initialize Docs
2. `/bmad-bmm-init-planning`
3. High-Level Product Brief
4. `/bmad-bmm-project-roadmap` -> `roadmap.md` and `roadmap.yaml`
5. `/bmad-bmm-phase-sync` -> `phase.md` and `phase-state.yaml`
6. `/bmad-bmm-initiative-routing` when execution scope is `workspace` or `orchestration`
7. Detailed Product Brief
8. `/bmad-bmm-create-prd`
9. `/bmad-bmm-create-architecture`
10. `/bmad-bmm-create-epics-and-stories`
11. `/bmad-bmm-check-implementation-readiness`
12. `/bmad-bmm-sprint-planning`
13. Story progression: `/bmad-bmm-create-story` -> `/bmad-bmm-dev-story`
14. `/bmad-bmm-phase-closeout`

## Supporting And Alternate Lanes

These are part of the operating model but not part of the main linear gate chain.

### Core

| Workflow | Command / Invocation |
| --- | --- |
| Brainstorming | `/bmad-brainstorming` |
| Party Mode | `/bmad-party-mode` |
| Help | `/bmad-help` |
| Index Docs | `/bmad-index-docs` |
| Shard Document | `/bmad-shard-doc` |
| Editorial Review - Prose | `/bmad-editorial-review-prose` |
| Editorial Review - Structure | `/bmad-editorial-review-structure` |
| Adversarial Review | `/bmad-review-adversarial-general` |

### BMM / CIS / TEA

| Workflow | Command / Invocation |
| --- | --- |
| Teach Me Testing | `/bmad-tea-teach-me-testing` |
| Sync Repositories | `/bmad-bmm-sync-repositories` |
| Workspace Bootstrap | `/bmad-bmm-workspace-bootstrap` |
| Generate Project Context | `/bmad-bmm-generate-project-context` |
| Quick Spec | `/bmad-bmm-quick-spec` |
| Quick Dev | `/bmad-bmm-quick-dev` |
| Correct Course | `/bmad-bmm-correct-course` |
| Problem Solving | `/bmad-cis-problem-solving` |
| Write Document | Load `/tech-writer`, then `WD` |
| Update Standards | Load `/tech-writer`, then `US` |
| Mermaid Generate | Load `/tech-writer`, then `MG` |
| Validate Document | Load `/tech-writer`, then `VD` |
| Update Docs | `/bmad-bmm-update-docs` |
| Validate Docs | `/bmad-bmm-validate-docs` |
| Explain Concept | Load `/tech-writer`, then `EC` |

### Automation Wrappers (Reference-Stage Orchestration Layer)

These wrappers orchestrate the workflow above. They do not replace the canonical human-readable gate chain.
They are intentionally documented in `_bmad/tools/automation/` rather than exposed through `module-help.csv` until they become real runtime commands.

| Workflow | Proposed Command | Notes |
| --- | --- | --- |
| Auto Plan | `auto-plan` | Wraps initialization, analysis, roadmap work, detailed analysis, planning, and solutioning up to readiness |
| Auto Epic Start | `auto-epic-start` | Wraps epic kickoff and baseline prep before story execution |
| Auto Story | `auto-story` | Wraps one story loop at a time |
| Auto Epic End | `auto-epic-end` | Wraps epic closeout, retro, and next-epic readiness |

### BMad Builder (Separate Lane; Not Part Of Product Delivery Flow)

`bmad-builder` workflows are module, agent, and workflow authoring tools.
They remain `anytime` and do not insert into the Compass delivery spine.

## Command Compatibility (TEA)

| Canonical Slash Alias | Alternate Colon Form |
| --- | --- |
| `/bmad-tea-teach-me-testing` | `/bmad:tea:teach-me-testing` |
| `/bmad-tea-testarch-test-design` | `/bmad:tea:test-design` |
| `/bmad-tea-testarch-framework` | `/bmad:tea:framework` |
| `/bmad-tea-testarch-ci` | `/bmad:tea:ci` |
| `/bmad-tea-testarch-atdd` | `/bmad:tea:atdd` |
| `/bmad-tea-testarch-automate` | `/bmad:tea:automate` |
| `/bmad-tea-testarch-test-review` | `/bmad:tea:test-review` |
| `/bmad-tea-testarch-nfr` | `/bmad:tea:nfr-assess` |
| `/bmad-tea-testarch-trace` | `/bmad:tea:trace` |

## Source Files And Inputs Audited

- `_bmad/bmm/module-help.csv`
- `_bmad/core/module-help.csv`
- `_bmad/bmm/**`
- `_bmad/core/**`
- `_bmad/BMAD-workflow.md`
- `planning/**`
- `planning/templates/**`
- `docs/**`
- shipped extension workflows already normalized into `_bmad/bmm/`
