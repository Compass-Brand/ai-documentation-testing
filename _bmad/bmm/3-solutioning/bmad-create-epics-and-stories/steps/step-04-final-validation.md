---
name: 'step-04-final-validation'
description: 'Validate complete coverage of all requirements and ensure implementation readiness'

# Path Definitions
workflow_path: '{project-root}/_bmad/bmm/3-solutioning/bmad-create-epics-and-stories'

# File References
thisStepFile: './step-04-final-validation.md'
workflowFile: '{workflow_path}/workflow.md'
outputFile: '{current_epics_dir}/epics.md'

# Task References
advancedElicitationTask: '{project-root}/_bmad/core/bmad-advanced-elicitation/workflow.xml'
partyModeWorkflow: '{project-root}/_bmad/core/bmad-party-mode/workflow.md'

# Template References
epicsTemplate: '{workflow_path}/templates/epics-template.md'
---

# Step 4: Final Validation

## STEP GOAL:

To validate complete coverage of all requirements and ensure stories are ready for development.

## MANDATORY EXECUTION RULES (READ FIRST):

### Universal Rules:

- 🛑 NEVER generate content without user input
- 📖 CRITICAL: Read the complete step file before taking any action
- 🔄 CRITICAL: Process validation sequentially without skipping
- 📋 YOU ARE A FACILITATOR, not a content generator
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

### Role Reinforcement:

- ✅ You are a product strategist and technical specifications writer
- ✅ If you already have been given communication or persona patterns, continue to use those while playing this new role
- ✅ We engage in collaborative dialogue, not command-response
- ✅ You bring validation expertise and quality assurance
- ✅ User brings their implementation priorities and final review

### Step-Specific Rules:

- 🎯 Focus ONLY on validating complete requirements coverage
- 🚫 FORBIDDEN to skip any validation checks
- 💬 Validate FR coverage, story completeness, and dependencies
- 🚪 ENSURE all stories are ready for development

## EXECUTION PROTOCOLS:

- 🎯 Validate every requirement has story coverage
- 💾 Check story dependencies and flow
- 📖 Verify architecture compliance
- 🚫 FORBIDDEN to approve incomplete coverage

## CONTEXT BOUNDARIES:

- Available context: Complete epic and story breakdown from previous steps
- Focus: Final validation of requirements coverage and story readiness
- Limits: Validation only, no new content creation
- Dependencies: Completed story generation from Step 3

## VALIDATION PROCESS:

### 1. FR Coverage Validation

Review the complete epic and story breakdown to ensure EVERY FR is covered:

**CRITICAL CHECK:**

- Go through each FR from the Requirements Inventory
- Verify it appears in at least one story
- Check that acceptance criteria fully address the FR
- No FRs should be left uncovered

### 2. Architecture Implementation Validation

**Check for Starter Template Setup:**

- Does Architecture document specify a starter template?
- If YES: Epic 1 Story 1 must be "Set up initial project from starter template"
- This includes cloning, installing dependencies, initial configuration

**Database/Entity Creation Validation:**

- Are database tables/entities created ONLY when needed by stories?
- ❌ WRONG: Epic 1 creates all tables upfront
- ✅ RIGHT: Tables created as part of the first story that needs them
- Each story should create/modify ONLY what it needs

### 3. Story Quality Validation

**Each story must:**

- Be completable by a single dev agent
- Have clear acceptance criteria
- Reference specific FRs it implements
- Include necessary technical details
- **Not have forward dependencies** (can only depend on PREVIOUS stories)
- Be implementable without waiting for future stories

### 4. Epic Structure Validation

**Check that:**

- Epics deliver user value, not technical milestones
- Dependencies flow naturally
- Foundation stories only setup what's needed
- No big upfront technical work

### 5. Dependency Validation (CRITICAL)

**Epic Independence Check:**

- Does each epic deliver COMPLETE functionality for its domain?
- Can Epic 2 function without Epic 3 being implemented?
- Can Epic 3 function standalone using Epic 1 & 2 outputs?
- ❌ WRONG: Epic 2 requires Epic 3 features to work
- ✅ RIGHT: Each epic is independently valuable

**Within-Epic Story Dependency Check:**
For each epic, review stories in order:

- Can Story N.1 be completed without Stories N.2, N.3, etc.?
- Can Story N.2 be completed using only Story N.1 output?
- Can Story N.3 be completed using only Stories N.1 & N.2 outputs?
- ❌ WRONG: "This story depends on a future story"
- ❌ WRONG: Story references features not yet implemented
- ✅ RIGHT: Each story builds only on previous stories

### 6. Complete and Save

If all validations pass:

- Update any remaining placeholders in the document
- Ensure proper formatting
- Save the final epics.md

**Present Final Menu:**
**All validations complete!** [C] Complete Workflow

When C is selected, the workflow is complete and the epics.md is ready for development.

**Downstream Sprint-Planning Output Contract:**

> Story descriptions must reference the actual shipped sprint-planning output contract.
> Verify paths and formats against the sprint-planning and sprint-status workflow definitions.

The next workflow in the implementation pipeline is `sprint-planning`, which:

- Reads epics from `{current_epics_dir}` (the output of this workflow)
- Generates `sprint-status.yaml` (a YAML file, not markdown) under `{current_story_dir}` -- the stories directory, not a separate `sprint-planning/` path
- Tracks epic/story status via the `sprint-status.yaml` artifact, not via document frontmatter
- Status transitions are governed by the `sprint-planning` and `sprint-status` workflows, not embedded in story documents

**Recommended next steps for the user:**

1. Run `/bmad-bmm-sprint-planning` to generate `sprint-status.yaml` from the epics
2. Run `/bmad-bmm-create-story` to create individual story files (reads from `sprint-status.yaml`)
3. Run `/bmad-bmm-dev-story` to implement stories

Epics and Stories complete. Read fully and follow: `{project-root}/_bmad/core/bmad-help/SKILL.md`

Upon Completion of task output: offer to answer any questions about the Epics and Stories.

## OVERSIGHT CAPTURE

When `{oversight_mode}` is `true`:

- If you identified any risk during this workflow (a dependency that might not hold, a scale concern, an integration uncertainty), append it to `{current_oversight_risks_file}`:
  ```yaml
  - id: risk-NNN  # increment from last entry, or risk-001 if file is empty
    summary: "<one-line description>"
    source_workflow: create-epics-and-stories
    source_step: step-04-final-validation
    raised_at: "{{date}}"
    status: draft
    severity: <low|medium|high|critical>
    mitigation: ""
    resolved_at: ""
  ```

- If you made or relied on any assumption that has not been verified (a technology capability, an environment constraint, a user behavior expectation), append it to `{current_oversight_assumptions_file}`:
  ```yaml
  - id: assumption-NNN  # increment from last entry, or assumption-001 if file is empty
    summary: "<one-line description>"
    source_workflow: create-epics-and-stories
    source_step: step-04-final-validation
    raised_at: "{{date}}"
    status: draft
    validated_by: ""
    resolved_at: ""
  ```

- Do not pause work to discuss these entries. Log and continue.
- If the files do not exist yet, create them with the entry as the first item.
