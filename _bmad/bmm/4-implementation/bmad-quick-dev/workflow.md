---
name: quick-dev
description: 'Implement a Quick Tech Spec for small changes or features. Use when the user provides a quick tech spec and says "implement this quick spec" or "proceed with implementation of [quick tech spec]"'
---

# Quick Dev Workflow

**Goal:** Execute implementation tasks efficiently, either from a tech-spec or direct user instructions.

**Your Role:** You are an elite full-stack developer executing tasks autonomously. Follow patterns, ship code, run tests. Every response moves the project forward.

---

## WORKFLOW ARCHITECTURE

This uses **step-file architecture** for focused execution:

- Each step loads fresh to combat "lost in the middle"
- State persists via variables: `{baseline_commit}`, `{execution_mode}`, `{tech_spec_path}`
- Sequential progression through implementation phases

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `user_name`, `communication_language`, `user_skill_level`
- `current_story_dir`, `current_evidence_dir`, `current_testing_dir`, `current_architecture_dir`
- `date` as system-generated current datetime
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

### Paths

- `installed_path` = `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev`
- `project_context` = `**/project-context.md` (load if exists)

### Related Workflows

- `quick_spec_workflow` = `{project-root}/_bmad/compass/4-implementation/bmad-compass-quick-spec/workflow.md`
- `party_mode_exec` = `{project-root}/_bmad/core/bmad-party-mode/workflow.md`
- `advanced_elicitation` = `{project-root}/_bmad/core/bmad-advanced-elicitation/workflow.xml`

---

## EXECUTION

Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-01-mode-detection.md` to begin the workflow.
