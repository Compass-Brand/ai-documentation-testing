---
name: oversight-checkpoint
description: 'Generate a verification report from the oversight risk and assumption registers. Use at gate approvals and story completion to surface unreviewed items.'
---

# Oversight Checkpoint Workflow

**Goal:** Surface unreviewed risks and assumptions before a gate approval or after story completion.

**Your Role:** You are a verification facilitator. Read the registers, generate the report, and present items for user review. Do not block — oversight is advisory.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `oversight_mode`
- `current_oversight_dir`
- `current_oversight_risks_file`
- `current_oversight_assumptions_file`
- `current_evidence_dir`
- `date` as a system-generated value (`YYYY-MM-DD`)

If `oversight_mode` is `false`, skip this workflow entirely and return.

## INPUTS

This workflow expects a `gate_name` parameter indicating which checkpoint triggered it. Valid values: `roadmap`, `prd`, `architecture`, `readiness`, `story-completion`.

## EXECUTION

1. Read `{current_oversight_risks_file}` and `{current_oversight_assumptions_file}`. If either file does not exist or is empty, note it and continue with whatever is available.

2. Categorize entries:
   - **Unreviewed**: `status: draft` — these need user attention
   - **Open confirmed risks**: `status: confirmed` with empty `mitigation` — acknowledged but unmitigated
   - **Resolved**: any entry with a non-empty `resolved_at` — no action needed

3. If there are no unreviewed items and no open confirmed risks, report "No oversight items require attention" and return without generating a file.

4. Generate the checkpoint report:

```
# Oversight Checkpoint: {{gate_name}}

**Generated:** {{date}}
**Gate:** {{gate_name}}
**Phase:** {{phase_id}}

## Unreviewed Items (draft)

### Risks
{{for each risk with status: draft}}
- **{{id}}** [{{severity}}]: {{summary}}
  - Source: {{source_workflow}} / {{source_step}}
  - Action needed: confirm or dismiss
{{end}}

### Assumptions
{{for each assumption with status: draft}}
- **{{id}}** [draft]: {{summary}}
  - Source: {{source_workflow}} / {{source_step}}
  - Action needed: confirm or invalidate
{{end}}

## Open Confirmed Risks

{{for each risk with status: confirmed and empty mitigation}}
- **{{id}}** [{{severity}}, confirmed]: {{summary}}
  - Mitigation: (none documented)
  - Action needed: document mitigation or accept risk
{{end}}

## Summary

| Category | Draft | Confirmed | Mitigated/Resolved |
|----------|-------|-----------|-------------------|
| Risks | {{count}} | {{count}} | {{count}} |
| Assumptions | {{count}} | {{count}} | {{count}} |

**Recommendation:** {{total unreviewed + unmitigated confirmed}} items require review before gate approval.
```

5. Write the report to `{current_evidence_dir}/oversight-checkpoint-{{gate_name}}.md`.

6. Present the report to the user inline and ask:
   - "Would you like to update any statuses before proceeding?"
   - If yes: accept user updates and write them back to the YAML files. When moving an item to a terminal status (`mitigated`, `dismissed`, `invalidated`), set `resolved_at` to the current date.
   - If no: proceed. Oversight is advisory, not blocking.

## OUTPUT RULES

- Do not generate a report if both register files are empty or missing.
- Do not block gate approval — always allow the user to proceed.
- Keep date format as `YYYY-MM-DD`.
- Preserve existing entries when appending or updating — never overwrite the full file.
