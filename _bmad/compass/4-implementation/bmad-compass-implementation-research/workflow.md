---
name: implementation-research
description: 'Targeted research for active implementation decisions. Use when the user says "research this implementation option" or "investigate before coding".'
---

# Implementation Research Workflow

**Goal:** Produce decision-ready implementation research for active epics/stories and store it in the current phase lane.

**Your Role:** You are a technical analyst focused on delivery risk reduction and decision clarity for in-flight implementation.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `current_research_dir`, `current_epics_dir`, `current_story_dir`
- `current_architecture_dir`, `current_prd_dir`, `current_testing_dir`
- `date` as a system-generated value (`YYYY-MM-DD`)

## EXECUTION

1. Define the research question tied to active implementation scope.
2. Load implementation context from active artifacts:
   - story/epic context and acceptance criteria
   - architecture constraints
   - relevant PRD intent
   - testing and quality gates
3. Investigate feasible options and document evidence:
   - option summary
   - compatibility with existing system
   - operational and testing implications
   - known risks and failure modes
4. Recommend a path with explicit rationale and rejected alternatives.
5. Save the report to:
   - `{current_research_dir}/implementation-research-{{date}}.md`
6. Add a follow-up section with actionable next command(s), such as:
   - `/bmad-bmm-create-story`
   - `/bmad-bmm-dev-story`
   - `/bmad-bmm-correct-course`

## OUTPUT RULES

- Keep implementation research in `{current_research_dir}`.
- Do not store implementation research in roadmap research lanes.
- Use absolute dates (`YYYY-MM-DD`) in filenames and metadata.
