---
name: 'workflow-specify'
description: 'Create a complete, implementation-ready page specification with layout, components, content, interactions, and states. Use when the user says "WDS write specification" or "WDS create page spec"'
---

# [P] Specify — Detail a Page Specification

**Goal:** Create a complete, implementation-ready page specification with layout, components, content, interactions, and states.

**When to use:** When a page structure exists (from Suggest, Dream, or Sketch) and needs full specification detail.

---

## INITIALIZATION

### Configuration Loading

Load and read full config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `user_name`, `communication_language`, `document_output_language`
- `current_outline_scenarios_dir`, `current_conceptual_specifications_dir`, `current_ux_agent_dialog_dir`

### Agent Dialog Gate

1. Check `{current_ux_agent_dialog_dir}/` for pending activity dialogs
2. If none, suggest creating one
3. Load dialog context


## Entry

Load page context from the approved scenario and UX artifacts in `{current_outline_scenarios_dir}/`, then write the resulting specification into `{current_conceptual_specifications_dir}/`.

## Steps

Execute steps in `./steps-p/`:

| Step | File | Purpose |
|------|------|---------|
| 01 | step-01-page-basics.md | Page metadata, purpose, entry points |
| 02 | step-02-layout-sections.md | Section layout and ordering |
| 03 | step-03-components-objects.md | Component/object definitions per section |
| 04 | step-04-content-languages.md | Content text and translations |
| 05 | step-05-interactions.md | User interactions and behaviors |
| 06 | step-06-states.md | Loading, error, empty states |
| 07 | step-07-validation.md | Form validation and constraints |
| 08 | step-08-generate-spec.md | Generate final specification document |

**Reference data:**
- `./data/object-types/` — component types and templates
- `./data/guides/WDS-SPECIFICATION-PATTERN.md` — specification format
- `./data/modular-architecture/` — three-tier architecture
- `./templates/page-specification.template.md` — output template

---

## AFTER COMPLETION

1. Update design log
2. Suggest the next action or continue to `Design Delivery`
3. Return to activity menu
