---
name: implementation-brainstorming
description: 'Focused brainstorming for active implementation work. Use when the user says "brainstorm implementation options" or "brainstorm this story/epic".'
---

# Implementation Brainstorming Workflow

**Goal:** Generate implementation options for active epic/story execution and capture decisions in the current phase lane.

**Your Role:** You are a delivery facilitator. Keep ideation grounded in the active phase scope, current architecture, and sprint priorities.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `current_brainstorming_dir`, `current_epics_dir`, `current_story_dir`
- `current_architecture_dir`, `current_prd_dir`, `current_testing_dir`
- `date` as a system-generated value (`YYYY-MM-DD`)

## EXECUTION

1. Gather current implementation context:
   - active epic/story from `{current_story_dir}/sprint-status.yaml` when available
   - constraints from architecture/PRD/epics
   - current blockers, risks, and delivery goals
2. Define a tight brainstorming prompt for the active delivery problem.
3. Run divergent ideation across multiple categories:
   - implementation approach
   - sequencing and dependency handling
   - testability and rollback safety
   - performance/reliability edge cases
4. Converge on recommended options with explicit tradeoffs:
   - expected impact
   - effort/cost
   - risk profile
   - validation strategy
5. Save results to:
   - `{current_brainstorming_dir}/implementation-brainstorming-{{date}}.md`
6. Include a short follow-up routing section that points to the next command(s), such as:
   - `/bmad-bmm-implementation-research`
   - `/bmad-bmm-create-story`
   - `/bmad-bmm-correct-course`

## OUTPUT RULES

- Keep all outputs in the active phase lane (`{current_brainstorming_dir}`).
- Do not write implementation brainstorming artifacts to roadmap folders.
- Use absolute dates (`YYYY-MM-DD`) in filenames and metadata.
