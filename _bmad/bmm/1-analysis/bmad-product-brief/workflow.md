---
name: create-product-brief
description: 'Create product brief through collaborative discovery. Use when the user says "lets create a product brief" or "help me create a project brief"'
---

# Product Brief Workflow

**Goal:** Create product briefs through collaborative step-by-step discovery while keeping the output grounded in the current target repo.

**Your Role:** In addition to your name, communication_style, and persona, you are also a product-focused Business Analyst collaborating with an expert peer. Keep the tone direct and professional. Avoid hype, cheerleading, or overly familiar language.

---

## WORKFLOW ARCHITECTURE

This uses **step-file architecture** for disciplined execution:

### Core Principles

- **Micro-file Design**: Each step is a self contained instruction file that is a part of an overall workflow that must be followed exactly
- **Just-In-Time Loading**: Only the current step file is in memory - never load future step files until told to do so
- **Sequential Enforcement**: Sequence within the step files must be completed in order, no skipping or optimization allowed
- **State Tracking**: Document progress in output file frontmatter using `stepsCompleted` array when a workflow produces a document
- **Append-Only Building**: Build documents by appending content as directed to the output file

### Step Processing Rules

1. **READ COMPLETELY**: Always read the entire step file before taking any action
2. **FOLLOW SEQUENCE**: Execute all numbered sections in order, never deviate
3. **WAIT FOR INPUT**: If a menu is presented, halt and wait for user selection
4. **CHECK CONTINUATION**: If the step has a menu with Continue as an option, only proceed to next step when user selects 'C' (Continue)
5. **SAVE STATE**: Update `stepsCompleted` in frontmatter before loading next step
6. **LOAD NEXT**: When directed, read fully and follow the next step file

### Critical Rules (NO EXCEPTIONS)

- 🛑 **NEVER** load multiple step files simultaneously
- 📖 **ALWAYS** read entire step file before execution
- 🚫 **NEVER** skip steps or optimize the sequence
- 💾 **ALWAYS** update frontmatter of output files when writing the final output for a specific step
- 🎯 **ALWAYS** follow the exact instructions in the step file
- ⏸️ **ALWAYS** halt at menus and wait for user input
- 📋 **NEVER** create mental todo lists from future steps

---

## INITIALIZATION SEQUENCE

### 1. Configuration Loading

Load and read full config from {project-root}/_bmad/bmm/module.yaml and resolve:

- `project_name`, `planning_root`, `planning_roadmap`, `roadmap_product_brief_dir`, `user_name`, `communication_language`, `document_output_language`, `user_skill_level`

Treat `project_name` in config as the source-bundle authoring name only. For any downstream output file names, document titles, and user-facing summaries, derive the target repo identity from the current `{project-root}` directory name instead. Do not leak `compass-engine` into downstream product-brief outputs unless the current repo actually is `compass-engine`.

If the current repo is clearly a disposable smoke-test or validation-only repo, keep the brief minimal and validation-scoped. Do not expand into broad product discovery when the user has already provided a narrow validation purpose.

### 2. First Step EXECUTION

Read fully and follow: `{project-root}/_bmad/bmm/1-analysis/bmad-product-brief/steps/step-01-init.md` to begin the workflow.
