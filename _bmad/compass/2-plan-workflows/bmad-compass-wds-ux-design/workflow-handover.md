---
name: handover
description: 'Package complete testable flows and hand off to development. Use when the user says "WDS handoff to development" or "WDS package for delivery"'
---

# [H] Handover — Package DD-XXX and Hand Off to BMad

**Goal:** Package a complete testable flow into a Design Delivery and hand off to development.

**When to use:** A scenario flow is fully designed, all specifications exist, and you are ready to hand off to BMad for implementation.

---

## INITIALIZATION

### Configuration Loading

Load and read full config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `user_name`, `communication_language`, `document_output_language`
- `current_conceptual_specifications_dir`, `current_design_delivery_dir`, `current_design_delivery_test_dir`
- `current_design_delivery_handoff_dir`, `current_ux_agent_dialog_dir`

### Agent Dialog Gate

1. Check `{current_ux_agent_dialog_dir}/` for pending handover dialogs
2. If none exists, suggest creating one for this handover
3. If exists, load and resume

---

## STEPS

Execute steps in `./steps-h/`:

| Step | File | Purpose |
|------|------|---------|
| 01 | step-01-detect-completion.md | Verify flow is complete and testable |
| 02 | step-02-create-delivery.md | Package into DD-XXX Design Delivery |
| 03 | step-03-create-test-scenario.md | Define validation tests |
| 04 | step-04-handoff-dialog.md | Structured handoff conversation with BMad |
| 05 | step-05-hand-off.md | Official handoff to BMad |
| 06 | step-06-continue.md | Return to design or next flow |

**Reference data:**
- `./data/delivery-templates.md`
- `./data/handoff-dialog-scripts.md`
- `./data/design-deliveries-guide.md`

---

## AFTER COMPLETION

1. Update design log
2. Suggest next agent dialog action
3. Return to the Compass WDS activity menu
