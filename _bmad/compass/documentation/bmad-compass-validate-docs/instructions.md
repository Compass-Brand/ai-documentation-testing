# Validate Docs Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/documentation/bmad-compass-validate-docs/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Validate documentation against the canonical Compass documentation framework, project-local overrides, and BMAD promotion rules.

## Step 1: Validate Required Structure

Verify presence of required layout:

- `{docs_root}/README.md`
- `{docs_architecture_dir}/README.md`
- `{docs_architecture_decisions_dir}/README.md`
- `{docs_development_dir}/README.md`
- `{docs_getting_started_dir}/README.md`
- `{docs_getting_started_dir}/installation.md`
- `{docs_getting_started_dir}/quickstart.md`
- `{docs_guides_dir}/README.md`
- `{docs_reference_dir}/README.md`
- `{docs_ai_root}/README.md`

## Step 2: Validate Policy Baseline Sync

- confirm baseline policy files exist in `{docs_human_policies_dir}`
- confirm baseline templates exist in `{docs_human_templates_dir}`
- confirm overrides file exists at `{docs_human_overrides_file}`
- confirm the installed baseline reflects the current framework source in `{docs_framework_human_policies_dir}` and `{docs_framework_human_templates_dir}`

## Step 3: Validate Governance And Lifecycle Rules

Check for:

- docs ownership or maintenance metadata in `{docs_root}/README.md`
- review cadence metadata for operational docs where expected
- lifecycle state notes on active human docs or explicit gaps captured for unresolved migration cases
- promotion evidence when planning artifacts have been turned into canonical docs

## Step 4: Validate Document-Type And Architecture Rules

Check for:

- README presence at each docs directory level
- one primary mode per guide or reference document
- cross-links between explanation, how-to, tutorial, and reference docs where relevant
- architecture overview presence
- relative internal links
- naming conventions (lowercase kebab-case for docs files)
- ADR naming convention under decisions (`0001-topic.md` pattern when ADRs exist)
- ADR status, context, decision, and consequences structure when ADRs exist

## Step 5: Validate Style And Quality Rules

Check for:

- no unresolved placeholders (`TODO`, `TBD`, `coming soon`)
- descriptive link text
- language identifiers on fenced code blocks
- consistent terminology across changed docs
- runnable or clearly marked illustrative command examples

## Step 6: Emit Validation Report

Write `{default_output_file}` with sections:

1. Structure checks (pass/fail)
2. Policy/template sync checks (pass/fail)
3. Governance and lifecycle checks (pass/warn/fail)
4. Diataxis and architecture checks (pass/warn/fail)
5. Style and quality checks (pass/warn/fail)
6. Blocking issues
7. Recommended remediation order

## Step 7: Gate Recommendation

End with gate recommendation:

- `PASS` if no blocking issues
- `CONCERNS` if only warnings
- `FAIL` if structure or policy blockers exist
