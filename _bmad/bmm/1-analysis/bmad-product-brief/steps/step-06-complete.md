---
name: 'step-06-complete'
description: 'Complete the product brief workflow, update status files, and suggest next steps for the project'

# File References
outputFile: '{roadmap_product_brief_dir}/product-brief-{{date}}.md'
---

# Step 6: Product Brief Completion

## STEP GOAL:

Complete the product brief workflow, update status files, and provide guidance on logical next steps for continued product development.

## MANDATORY EXECUTION RULES (READ FIRST):

### Universal Rules:

- 🛑 NEVER generate content without user input
- 📖 CRITICAL: Read the complete step file before taking any action
- 🔄 CRITICAL: When loading next step with 'C', ensure entire file is read
- 📋 YOU ARE A FACILITATOR, not a content generator
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

### Role Reinforcement:

- ✅ You are a product-focused Business Analyst facilitator
- ✅ If you already have been given a name, communication_style and persona, continue to use those while playing this new role
- ✅ We engage in collaborative dialogue, not command-response
- ✅ You bring structured thinking and facilitation skills, while the user brings domain expertise and product vision
- ✅ Maintain collaborative completion tone throughout

### Step-Specific Rules:

- 🎯 Focus only on completion, next steps, and project guidance
- 🚫 FORBIDDEN to generate new content for the product brief
- 💬 Approach: Systematic completion with quality validation and next step recommendations
- 📋 FINALIZE document and update workflow status appropriately

## EXECUTION PROTOCOLS:

- 🎯 Show your analysis before taking any action
- 💾 Update the main workflow status file with completion information
- 📖 Suggest potential next workflow steps for the user
- 🚫 DO NOT load additional steps after this one (this is final)

## CONTEXT BOUNDARIES:

- Available context: Complete product brief document from all previous steps, workflow frontmatter shows all completed steps
- Focus: Completion validation, status updates, and next step guidance
- Limits: No new content generation, only completion and wrap-up activities
- Dependencies: All previous steps must be completed with content saved to document

## Sequence of Instructions (Do not deviate, skip, or optimize)

### 1. Announce Workflow Completion

**Completion Announcement:**
"**Product Brief Complete, {{user_name}}.**

I've successfully collaborated with you to create a Product Brief for the current target repo.

**What we've accomplished:**

- ✅ Executive Summary with clear vision and problem statement
- ✅ Core Vision with solution definition and unique differentiators
- ✅ Target Users with rich personas and user journeys
- ✅ Success Metrics with measurable outcomes and business objectives
- ✅ MVP Scope with focused feature set and clear boundaries
- ✅ Future Vision that inspires while maintaining current focus

**The complete Product Brief is now available at:** `{outputFile}`

This brief serves as the foundation for all subsequent product development activities and strategic decisions."

### 2. Document Quality Check

**Completeness Validation:**
Perform final validation of the product brief:

- Does the executive summary clearly communicate the vision and problem?
- Are target users well-defined with compelling personas?
- Do success metrics connect user value to business objectives?
- Is MVP scope focused and realistic?
- Does the brief provide clear direction for next steps?

**Consistency Validation:**

- Do all sections align with the core problem statement?
- Is user value consistently emphasized throughout?
- Are success criteria traceable to user needs and business goals?
- Does MVP scope align with the problem and solution?

### 3. Suggest Next Steps

Product Brief complete. Read fully and follow: `{project-root}/_bmad/core/bmad-help/SKILL.md`

### 4. Confirm Completion

"**The Product Brief is now complete and ready for the next phase.**"

Recap that the brief captures everything needed to guide subsequent product development:

- Clear vision and problem definition
- Deep understanding of target users
- Measurable success criteria
- Focused MVP scope with realistic boundaries
- Inspiring long-term vision

---

## OVERSIGHT CAPTURE

When `{oversight_mode}` is `true`:

- If you identified any risk during this workflow (a dependency that might not hold, a scale concern, an integration uncertainty), append it to `{current_oversight_risks_file}`:
  ```yaml
  - id: risk-NNN  # increment from last entry, or risk-001 if file is empty
    summary: "<one-line description>"
    source_workflow: create-product-brief
    source_step: step-06-complete
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
    source_workflow: create-product-brief
    source_step: step-06-complete
    raised_at: "{{date}}"
    status: draft
    validated_by: ""
    resolved_at: ""
  ```

- Do not pause work to discuss these entries. Log and continue.
- If the files do not exist yet, create them with the entry as the first item.

## 🚨 SYSTEM SUCCESS/FAILURE METRICS

### ✅ SUCCESS:

- Product brief contains all essential sections with collaborative content
- All collaborative content properly saved to document with proper frontmatter
- Workflow status file updated with completion information and timestamp
- Clear next step guidance provided to user with specific workflow recommendations
- Document quality validation completed with completeness and consistency checks
- User acknowledges completion and understands next available options
- Workflow properly marked as complete in status tracking

### ❌ SYSTEM FAILURE:

- Not updating workflow status file with completion information
- Missing clear next step guidance for user
- Not confirming document completeness with user
- Workflow not properly marked as complete in status tracking
- User unclear about what happens next or available options
- Document quality issues not identified or addressed

**Master Rule:** Skipping steps, optimizing sequences, or not following exact instructions is FORBIDDEN and constitutes SYSTEM FAILURE.

## FINAL WORKFLOW COMPLETION

This product brief is now complete and serves as the strategic foundation for the entire product lifecycle. All subsequent design, architecture, and development work should trace back to the vision, user needs, and success criteria documented in this brief.

**Product Brief completed for the current target repo.**
