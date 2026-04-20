# Compass BMAD Workflow Map

The complete ordered workflow for Compass BMAD. Read top to bottom.

Run **Part A** once at project start. Then repeat **Part B** for each approved roadmap slice.

## Legend

- **Required** — Part of the canonical progression. Cannot skip without breaking the spine.
- **Optional** — Valid in-order step you can skip without breaking the spine.
- **Conditional** — Runs when the lane is activated by project characteristics or explicit choice.
- **Planned** — Approved step that currently uses planning templates rather than a dedicated slash command.
- ↩ — This step also runs elsewhere in the workflow (cross-reference provided).
- ↻ — Loop boundary. Repeat the enclosed steps for each item.
- ⚑ — Conditional lane marker. The steps beneath activate only when indicated.

---

## Part A: Project-Level Setup And Direction

> Run once at project start or when re-baselining.

### §1. Initialization

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Sync Repositories | `/bmad-bmm-sync-repositories` | Conditional |
| 2 | Workspace Bootstrap | `/bmad-bmm-workspace-bootstrap` | Conditional |
| 3 | Initialize Docs | `/bmad-bmm-init-docs` | Required |
| 4 | Initialize Planning | `/bmad-bmm-init-planning` | Required |
| 5 | Generate / Seed Project Context | `/bmad-bmm-generate-project-context` | Conditional |
|   | | ↩ _Runs again in §5 step 1 at detailed scope_ | |

- Steps 1-2 are only needed for polyrepo workspaces or orchestration roots.
- Brownfield projects should generate context early (step 5). Greenfield projects should defer until after high-level framing in §2.

### §2. High-Level Analysis

> Preserves long-horizon thinking beyond the current slice.

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | High-Level Brainstorm | `/bmad-brainstorming` | Required |
|   | | ↩ _Runs again in §5 step 2 at detailed scope_ | |
| 2 | High-Level Market Research | `/bmad-bmm-market-research` | Required |
|   | | ↩ _Runs again in §5 step 3 at detailed scope_ | |
| 3 | High-Level Domain Research | `/bmad-bmm-domain-research` | Required |
|   | | ↩ _Runs again in §5 step 4 at detailed scope_ | |
| 4 | High-Level Technical Research | `/bmad-bmm-technical-research` | Required |
|   | | ↩ _Runs again in §5 step 5 at detailed scope_ | |
| 5 | High-Level Innovation Strategy | `/bmad-cis-innovation-strategy` | Required |
|   | | ↩ _Runs again in §5 step 6 at detailed scope_ | |
| 6 | High-Level Opportunity Framing | `/bmad-cis-design-thinking` | Required |
|   | | ↩ _Runs again in §5 step 7 at detailed scope_ | |
| 7 | High-Level Storytelling | Planned / Template-Driven | Conditional |
| 8 | High-Level Product Brief | `/bmad-bmm-create-product-brief` | Required |
|   | | ↩ _Runs again in §5 step 8 at detailed scope_ | |

- These outputs are roadmap-level artifacts, not one giant strategy document.
- Steps 1-6 and 8 all run again in §5 scoped to the active slice.

### §3. Project Roadmap

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Create / Update Roadmap Proposal | `/bmad-bmm-project-roadmap` | Required |
| 2 | Approve Slices | Approval checkpoint inside step 1 | Required |
| 3 | Write Approved Roadmap Summary | `/bmad-bmm-project-roadmap` | Required |

- Produces `roadmap.md` (human-readable) and `roadmap.yaml` (machine-readable source of truth).
- Only approved state belongs in `roadmap.yaml`.

---

## Part B: Per-Phase Execution Loop

> Repeat for each approved roadmap slice.

### §4. Phase Sync

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Phase Sync | `/bmad-bmm-phase-sync` | Required |

- Selects and frames the active roadmap slice.
- Produces `phase.md` and `phase-state.yaml`.

> ⚑ **Conditional: Workspace / Orchestration scope only**

| # | Step | Command | Gate |
|---|------|---------|------|
| 1a | Initiative Routing | `/bmad-bmm-initiative-routing` | Conditional |

- Fans the active phase into concurrent repo-targeted initiative workstreams.
- Every targeted repo still runs its own repo-local Phase Sync.

### §5. Detailed Analysis

> Same research lanes as §2, now scoped to the active roadmap slice.

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Generate / Refresh Project Context | `/bmad-bmm-generate-project-context` | Required |
|   | | ↩ _Initial pass in §1 step 5_ | |
| 2 | Detailed Brainstorm | `/bmad-brainstorming` | Required |
|   | | ↩ _High-level pass in §2 step 1_ | |
| 3 | Detailed Market Research | `/bmad-bmm-market-research` | Required |
|   | | ↩ _High-level pass in §2 step 2_ | |
| 4 | Detailed Domain Research | `/bmad-bmm-domain-research` | Required |
|   | | ↩ _High-level pass in §2 step 3_ | |
| 5 | Detailed Technical Research | `/bmad-bmm-technical-research` | Required |
|   | | ↩ _High-level pass in §2 step 4_ | |
| 6 | Detailed Innovation Strategy | `/bmad-cis-innovation-strategy` | Required |
|   | | ↩ _High-level pass in §2 step 5_ | |
| 7 | Detailed Opportunity Framing | `/bmad-cis-design-thinking` | Required |
|   | | ↩ _High-level pass in §2 step 6_ | |
| 8 | Detailed Product Brief | `/bmad-bmm-create-product-brief` | Required |
|   | | ↩ _High-level pass in §2 step 8_ | |

- Brownfield should inherit prior lessons but refresh assumptions against current repo reality.

### §6. Planning And Experience Design

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Create PRD | `/bmad-bmm-create-prd` | Required |
| 2 | Validate PRD | `/bmad-bmm-validate-prd` | Required |
| 3 | Edit PRD | `/bmad-bmm-edit-prd` | Conditional |

> ⚑ **Conditional: WDS lane — activates when workflows, user journeys, UX complexity, or behavior design matter**

| # | Step | Command | Gate |
|---|------|---------|------|
| 4 | Trigger Mapping | `/bmad-wds-trigger-mapping` | Conditional |
| 5 | Outline Scenarios | `/bmad-wds-outline-scenarios` | Conditional |
| 6 | Create UX Design | `/bmad-bmm-create-ux-design` | Conditional |
| 7 | Conceptual Specifications | `/bmad-wds-conceptual-specs` | Conditional |
| 8 | Design Delivery | `/bmad-wds-design-delivery` | Conditional |

- If WDS exposes requirement gaps, route back to step 3 (Edit PRD) before proceeding to §7.

| # | Step | Command | Gate |
|---|------|---------|------|
| 9 | Update Docs (Planning) | `/bmad-bmm-update-docs` | Optional |
|   | | ↩ _Also runs in §7 step 10 and §8D step 1_ | |

### §7. Solutioning

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Create Architecture | `/bmad-bmm-create-architecture` | Required |

> ⚑ **Conditional: CYBERSEC lane — activates for legacy auth, data flows, inherited attack surface, regulated work**

| # | Step | Command | Gate |
|---|------|---------|------|
| 2 | Threat Modeling | `/bmad-cybersec-threat-modeling` | Conditional |
| 3 | Security Architecture Review | `/bmad-cybersec-security-architecture-review` | Conditional |

- CYBERSEC runs after an initial architecture draft, not before.

| # | Step | Command | Gate |
|---|------|---------|------|
| 4 | Test Design (System-Level) | `/bmad-tea-testarch-test-design` | Optional |
|   | | ↩ _Runs again in §8B step 2 at epic level_ | |
| 5 | Create Epics and Stories | `/bmad-bmm-create-epics-and-stories` | Required |

> ⚑ **Conditional: TEA lane — test engineering steps**

| # | Step | Command | Gate |
|---|------|---------|------|
| 6 | Test Framework Setup | `/bmad-tea-testarch-framework` | Optional |
| 7 | CI/CD Alignment | `/bmad-tea-testarch-ci` | Optional |

> ⚑ **Conditional: CYBERSEC gate**

| # | Step | Command | Gate |
|---|------|---------|------|
| 8 | Secure Readiness Gate | `/bmad-cybersec-secure-gates` | Conditional |
|   | | ↩ _Runs again in §9 step 4 as secure release gate_ | |

| # | Step | Command | Gate |
|---|------|---------|------|
| 9 | Check Implementation Readiness | `/bmad-bmm-check-implementation-readiness` | Required |
| 10 | Update Docs (Solutioning) | `/bmad-bmm-update-docs` | Optional |
|    | | ↩ _Also runs in §6 step 9 and §8D step 1_ | |

### §8. Implementation

#### §8A. Sprint Kickoff

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Sprint Planning | `/bmad-bmm-sprint-planning` | Required |
| 2 | Sprint Status | `/bmad-bmm-sprint-status` | Optional |
|   | | ↩ _Also runs in §8C step 10, §8D step 3, and §9 step 6_ | |

#### §8B. Epic Loop

> ↻ Repeat for each epic in the sprint.

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Implementation Brainstorming | `/bmad-bmm-implementation-brainstorming` | Optional |
| 2 | Test Design (Epic-Level) | `/bmad-tea-testarch-test-design` | Optional |
|   | | ↩ _System-level pass in §7 step 4_ | |
| 3 | Implementation Research | `/bmad-bmm-implementation-research` | Optional |

- Best used for epics with delivery risk, unknowns, or multiple approaches.

#### §8C. Story Loop

> ↻ Repeat for each story in the current epic.

| # | ID | Step | Command | Gate |
|---|-----|------|---------|------|
| 1 | CS | Create Story | `/bmad-bmm-create-story` | Required |
| 2 | VS | Validate Story | `/bmad-bmm-create-story` (validate mode) | Required |
| 3 | AT | ATDD | `/bmad-tea-testarch-atdd` | Optional |
| 4 | DS | Dev Story | `/bmad-bmm-dev-story` | Required |
| 5 | TA | Test Automation | `/bmad-tea-testarch-automate` | Optional |
| 6 | QA | QA Automation Test | `/bmad-bmm-qa-automate` | Optional |
| 7 | CR | Code Review | `/bmad-bmm-code-review` | Optional |
| 8 | RV | Test Review | `/bmad-tea-testarch-test-review` | Optional |
| 9 | TR | Traceability | `/bmad-tea-testarch-trace` | Optional |
| 10 | SS | Sprint Status | `/bmad-bmm-sprint-status` | Optional |
|    |    | | ↩ _Also runs in §8A step 2, §8D step 3, and §9 step 6_ | |

**Story loop routing:**
1. CS → VS → AT → reuse check → DS
2. TA → QA (if needed) → CR
3. RV → TR → SS as needed
4. If review or gate fails, route back to DS and repeat downstream steps.

- Before DS, check for reuse of existing components, services, queries, patterns, and data access paths.
- TA is the preferred default post-dev automation lane. QA is a secondary expansion lane.
- Code Review (CR) runs before Test Review (RV).

#### §8D. Epic Wrap-Up

> Runs after all stories in the current epic are complete.

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Update Docs (Implementation) | `/bmad-bmm-update-docs` | Optional |
|   | | ↩ _Also runs in §6 step 9 and §7 step 10_ | |
| 2 | Retrospective | `/bmad-bmm-retrospective` | Optional |
| 3 | Sprint Status | `/bmad-bmm-sprint-status` | Optional |
|   | | ↩ _Also runs in §8A step 2, §8C step 10, and §9 step 6_ | |

### §9. Release Gate

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | NFR Assessment | `/bmad-tea-testarch-nfr` | Optional |
| 2 | Final Test Review | `/bmad-tea-testarch-test-review` | Optional |
| 3 | Traceability Gate | `/bmad-tea-testarch-trace` | Optional |
| 4 | Secure Release Gate | `/bmad-cybersec-secure-gates` | Conditional |
|   | | ↩ _Readiness pass in §7 step 8_ | |
| 5 | Validate Docs | `/bmad-bmm-validate-docs` | Optional |
| 6 | Sprint Status | `/bmad-bmm-sprint-status` | Optional |
|   | | ↩ _Also runs in §8A step 2, §8C step 10, and §8D step 3_ | |

- Release gating should collect evidence rather than rely on intuition.

### §10. Phase Closeout

| # | Step | Command | Gate |
|---|------|---------|------|
| 1 | Phase Closeout | `/bmad-bmm-phase-closeout` | Required |

- Archives the active slice, extracts lessons, updates roadmap state, and recreates the next clean `current/` scaffold.
- After closeout, return to §4 (Phase Sync) for the next approved roadmap slice.

---

## Required Spine

The minimal progression chain. Everything else enriches these gates.

1. Initialize Docs — `/bmad-bmm-init-docs`
2. Initialize Planning — `/bmad-bmm-init-planning`
3. High-Level Product Brief — `/bmad-bmm-create-product-brief`
4. Project Roadmap — `/bmad-bmm-project-roadmap`
5. Phase Sync — `/bmad-bmm-phase-sync`
6. Initiative Routing — `/bmad-bmm-initiative-routing` _(workspace/orchestration scope only)_
7. Detailed Product Brief — `/bmad-bmm-create-product-brief`
8. Create PRD — `/bmad-bmm-create-prd`
9. Create Architecture — `/bmad-bmm-create-architecture`
10. Create Epics and Stories — `/bmad-bmm-create-epics-and-stories`
11. Check Implementation Readiness — `/bmad-bmm-check-implementation-readiness`
12. Sprint Planning — `/bmad-bmm-sprint-planning`
13. Story Cycle — `/bmad-bmm-create-story` → `/bmad-bmm-dev-story`
14. Phase Closeout — `/bmad-bmm-phase-closeout`

---

## Supporting Lanes

Available anytime. Not part of the main progression.

### Core Utilities

| Code | Skill | Purpose |
|------|-------|---------|
| BSP | `/bmad-brainstorming` | Guided facilitation through brainstorming techniques |
| PM | `/bmad-party-mode` | Multi-agent discussions for multiple perspectives |
| BH | `/bmad-help` | Context-aware next-step recommendations |
| WM | `/bmad-compass-workflow-map` | This document — full workflow reference |
| ID | `/bmad-index-docs` | Index docs without loading everything |
| SD | `/bmad-shard-doc` | Split large docs (>500 lines) into manageable pieces |
| EP | `/bmad-editorial-review-prose` | Polish written content |
| ES | `/bmad-editorial-review-structure` | Improve document structure |
| AR | `/bmad-review-adversarial-general` | Quality assurance and deliverable review |
| ECH | `/bmad-review-edge-case-hunter` | Orthogonal coverage alongside adversarial review |
| DG | `/bmad-distillator` | Token-efficient distillates for downstream LLM use |

### BMM Utilities

| Code | Skill | Purpose |
|------|-------|---------|
| DP | `/bmad-document-project` | Analyze existing project to produce documentation |
| GPC | `/bmad-bmm-generate-project-context` | Scan codebase for LLM-optimized project context |
| QQ | `/bmad-bmm-quick-dev` | Unified intent-in code-out workflow |
| QS | `/bmad-bmm-quick-spec` | Quick specification generation |
| CC | `/bmad-bmm-correct-course` | Navigate significant changes to plan |
| PS | `/bmad-cis-problem-solving` | Structured problem-solving facilitation |

### Tech Writer Actions

| Code | Action | Purpose |
|------|--------|---------|
| WD | Load `/tech-writer`, then `WD` | Write a document following best practices |
| US | Load `/tech-writer`, then `US` | Update documentation standards |
| MG | Load `/tech-writer`, then `MG` | Create Mermaid diagrams |
| VD | Load `/tech-writer`, then `VD` | Validate document against standards |
| EC | Load `/tech-writer`, then `EC` | Explain complex concepts clearly |

### TEA (Test Engineering)

| Code | Skill | Purpose |
|------|-------|---------|
| TMT | `/bmad-tea-teach-me-testing` | Interactive testing education and guidance |

### Compass Extensions

| Code | Skill | Purpose |
|------|-------|---------|
| AE | `/bmad-compass-advanced-elicitation` | Push LLM to reconsider and refine output |
| ORL | `/bmad-compass-autonomous-refinement-loop` | Autonomous agent-team refinement loop |

### BMad Builder (Authoring Tools)

| Code | Skill | Purpose |
|------|-------|---------|
| AB | `/bmad-agent-builder` | Create, edit, and validate BMAD agents |
| MB | `/bmad-module-builder` | Create, edit, and validate BMAD modules |
| WB | `/bmad-workflow-builder` | Create, edit, and validate BMAD workflows |

---

## Steps That Intentionally Run Twice

| Step | First Pass | Second Pass | Why |
|------|-----------|-------------|-----|
| Brainstorming | §2.1 — roadmap scope | §5.2 — active slice scope | Preserves long-horizon thinking separately from focused delivery |
| Market Research | §2.2 — roadmap scope | §5.3 — active slice scope | Same |
| Domain Research | §2.3 — roadmap scope | §5.4 — active slice scope | Same |
| Technical Research | §2.4 — roadmap scope | §5.5 — active slice scope | Same |
| Innovation Strategy | §2.5 — roadmap scope | §5.6 — active slice scope | Same |
| Opportunity Framing | §2.6 — roadmap scope | §5.7 — active slice scope | Same |
| Product Brief | §2.8 — roadmap scope | §5.8 — active slice scope | Same |
| Generate Project Context | §1.5 — seed/brownfield | §5.1 — refresh for active slice | Context evolves as project matures |
| Test Design | §7.4 — system level | §8B.2 — epic level | Different granularity per stage |
| Secure Gates | §7.8 — readiness gate | §9.4 — release gate | Pre-implementation vs pre-release checkpoints |
| Update Docs | §6.9, §7.10, §8D.1 | Three passes | Planning, solutioning, and implementation each produce docs |
| Sprint Status | §8A.2, §8C.10, §8D.3, §9.6 | Four passes | Periodic checkpoint throughout implementation and release |
