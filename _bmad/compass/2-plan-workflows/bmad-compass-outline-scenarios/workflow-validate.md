---
name: scenarios-validate
description: 'Validate UX scenario outlines against WDS quality standards. Use when the user says "WDS validate scenarios" or "WDS check scenario quality"'
web_bundle: true
validateWorkflow: './steps-v/step-01-scenario-coverage.md'
---

# Validate UX Scenarios

**Goal:** Systematically validate all scenario outlines against WDS quality standards and generate an actionable report.

**Your Role:** Validation specialist reviewing scenario quality, coverage, and consistency.

---

## INITIALIZATION

### Agent Dialog Gate

1. Check for pending activity dialogs
2. If none, suggest creating one
3. Load dialog context

### Configuration Loading

Load and read full config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `user_name`, `communication_language`, `document_output_language`
- `current_trigger_mapping_dir`, `current_outline_scenarios_dir`

### Load Scenario Files

Load all scenario files from `{current_outline_scenarios_dir}/` and the scenario index `00-ux-scenarios.md`.

### Route to Validation

Load, read completely, and execute `{validateWorkflow}` (steps-v/step-01-scenario-coverage.md)

Auto-proceed through all validation steps. Present final report at the end.

---

## AFTER COMPLETION

1. Update design log
2. Suggest the next action in the Compass WDS lane
3. Return to activity menu
