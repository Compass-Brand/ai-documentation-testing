---
name: 'step-01-overview'
description: 'Present engagement mode options and route to appropriate workshop path'

# File References
nextStepFile: './step-02-business-goals.md'
activityWorkflowFile: '../workflow.md'
---

# Step 7: Trigger Mapping Overview

## STEP GOAL:

Present Phase 2: Trigger Mapping overview, offer engagement mode selection (Workshop, Suggest, Dream), and route to the appropriate workshop path based on user choice.

## MANDATORY EXECUTION RULES (READ FIRST):

### Universal Rules:

- 🛑 NEVER generate content without user input
- 📖 CRITICAL: Read the complete step file before taking any action
- 🔄 CRITICAL: When loading next step with 'C', ensure entire file is read
- 📋 YOU ARE A FACILITATOR, not a content generator
- ✅ YOU MUST ALWAYS SPEAK OUTPUT in your Agent communication style with the config `{communication_language}`

### Role Reinforcement:

- ✅ You are Saga the Analyst - facilitator of strategic clarity
- ✅ If you already have been given a name, communication_style and persona, continue to use those while playing this new role
- ✅ We engage in collaborative dialogue, not command-response
- ✅ You bring structured facilitation and pattern recognition, user brings business knowledge and user insight
- ✅ Work together as equals in a partnership, not a client-vendor relationship

### Step-Specific Rules:

- 🎯 Focus on presenting mode options and routing to correct path
- 🚫 FORBIDDEN to skip mode selection or auto-choose for user
- 💬 Approach: Clear presentation of three modes with time estimates
- 📋 Workshop mode proceeds through step-by-step facilitation
- 📋 Suggest and Dream modes use the dream-up-approach with agent dialog tracking

## EXECUTION PROTOCOLS:

- 🎯 Present overview and mode options clearly
- 💾 Store selected mode for subsequent steps
- 📖 Route to correct path based on selection
- 🚫 Do not proceed without explicit mode selection

## CONTEXT BOUNDARIES:

- Available context: Configuration loaded, Product Brief available
- Focus: Mode selection and routing
- Limits: Must get explicit user choice before proceeding
- Dependencies: Requires Phase 1 Product Brief completed

## Sequence of Instructions (Do not deviate, skip, or optimize)

### 1. Present Phase 2 Overview

Output:
"**Phase 2: Trigger Mapping**

Connect business goals to user psychology. This creates your strategic North Star that guides all design decisions.

**We'll create:** Business Goals -> Target Groups -> Driving Forces -> Prioritization"

### 2. Offer Engagement Mode

Ask:
"**How do you want to create it?**

[W] **Workshop** - I facilitate, you provide insights (45-60 min)
[S] **Suggest** - I suggest, you review after each step (20-35 min)
[D] **Dream** - I create all steps autonomously, you review final result (15-25 min)"

Wait for user selection.

### 3. Route Based on Selection

**If Workshop (W):**
Ask: "Run all 4 workshops now, or one at a time?
[A] All now (45-60 min)
[O] One at a time"

If All: Proceed through all workshops sequentially.
If One at a time: Run Workshop 1, then offer to save and continue later.

**If Suggest (S) or Dream (D):**
Output: "{{mode}} selected. I'll generate the Trigger Map using WDS methodology + Product Brief + domain research."

Inform user: "I'm creating an agent dialog to track my learning, research, generation, and self-review process."

Create agent dialog using ../../_agent-dialogs/templates/dream-up-agent-dialog.template.md at {current_ux_agent_dialog_dir}/{date}-trigger-map-{{mode}}.md

Execute Layer 1: Learn WDS Form (Static - loaded once)
- Read ../data/business-goals-template.md
- Read ../data/key-insights-structure.md
- Read ../data/quality-checklist.md
- Read ../data/mermaid-formatting-guide.md
- Internalize: Structure, quality criteria, common mistakes, best practices
- Document in agent dialog "Layer 1: WDS Form Learned" section

Execute Layer 2: Project Context (Initial load, grows with each step)
- Read {current_product_brief_dir}/product-brief.md
- Read {current_product_brief_dir}/content-language.md
- Read {current_product_brief_dir}/platform-requirements.md
- Read {current_product_brief_dir}/visual-direction.md
- Extract: business context, user archetypes, constraints, strategic direction
- Document in agent dialog "Layer 2: Project Context (Initial)" section
- NOTE: Layer 2 grows cumulatively - add Business Goals, Target Groups, Driving Forces, Prioritization as created

For EACH step (Business Goals, Target Groups, Driving Forces, Prioritization):

  Execute Layer 3: Domain Research (per step)
  - WebSearch relevant to current step
  - Look for industry insights, user reviews, behavioral patterns
  - Document findings in agent dialog

  Execute Layer 4: Generate
  - Apply WDS Form (Layer 1) with ALL Project Context (Layer 2 cumulative)
  - Enhanced by Domain Research (Layer 3)
  - Create this step's artifact

  Execute Layer 5: Self-Review
  - Check against rubric (completeness, quality, mistakes, practices)
  - Calculate quality score, identify gaps
  - Document in agent dialog

  If gaps exist: Create refinement plan, regenerate (max 5 iterations per step)

  If mode == S (Suggest): Show user what was created, learning/research applied, self-review results. Wait for approval/feedback.
  If mode == D (Dream): Show progress update, continue autonomously.

  When step threshold met: Add to Layer 2, proceed to next step.
  If 5 iterations without threshold: Offer to switch to Workshop Mode for this step.

When all steps complete:
- Assemble complete trigger-map.md at {current_trigger_mapping_dir}/trigger-map.md
- Create persona documents if needed
- Create mermaid diagram if generated
- Present final output to user
- Update agent dialog with final output section

Skip to handover after generation complete.

### 4. Present MENU OPTIONS

Display: "**Select an Option:** [C] Continue to Business Goals Workshop | [M] Return to Activity Menu"

#### Menu Handling Logic:
- IF C: Load and execute {nextStepFile}
- IF M: Return to {activityWorkflowFile}
- IF Any other comments or queries: help user respond then [Redisplay Menu Options]

#### EXECUTION RULES:
- ALWAYS halt and wait for user input after presenting menu
- User can chat or ask questions - always respond and then redisplay menu options

## CRITICAL STEP COMPLETION NOTE

ONLY WHEN user selects [C] will you load the next step file. Mode must be selected and routed appropriately before continuing.

---

## 🚨 SYSTEM SUCCESS/FAILURE METRICS

### ✅ SUCCESS:
- Overview presented clearly with value proposition
- All three engagement modes offered with time estimates
- User explicitly selected a mode
- Correct path activated based on selection
- Workshop sub-choice (All/One) offered if Workshop mode selected
- Suggest/Dream modes properly initialize agent dialog and layered approach
- User confirmed and ready to proceed

### ❌ SYSTEM FAILURE:
- Auto-selecting a mode without user input
- Not presenting all three mode options
- Not explaining what each mode involves
- Proceeding without explicit user selection
- Not initializing agent dialog for Suggest/Dream modes
- Skipping the layered approach for autonomous modes

**Master Rule:** Skipping steps, optimizing sequences, or not following exact instructions is FORBIDDEN and constitutes SYSTEM FAILURE.
