---
name: trigger-mapping-validate
description: 'Validate Trigger Map documents against WDS quality standards. Use when the user says "WDS validate trigger map" or "WDS check trigger mapping"'
web_bundle: true
validateWorkflow: './steps-v/step-01-target-group-coverage.md'
---

# Validate Trigger Map

**Goal:** Systematically validate all Trigger Map documents against WDS quality standards and generate an actionable report.

**Your Role:** Validation specialist reviewing trigger map completeness, consistency, and strategic alignment.

---

## INITIALIZATION

### Agent Dialog Gate

1. Check for pending activity dialogs
2. If none, suggest creating one
3. Load dialog context

### Configuration Loading

Load and read full config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `user_name`, `communication_language`, `document_output_language`
- `current_trigger_mapping_dir`

### Load Trigger Map Data

Load all trigger map documents from `{current_trigger_mapping_dir}/`.

### Route to Validation

Load, read completely, and execute `{validateWorkflow}` (steps-v/step-01-target-group-coverage.md)

Auto-proceed through all validation steps. Present final report at the end.

---

## AFTER COMPLETION

1. Update design log
2. Suggest the next action in the Compass WDS lane
3. Return to activity menu
