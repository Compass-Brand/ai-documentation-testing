---
name: vtc-workshop
description: 'Facilitate VTC workshop connecting business goals to user needs. Use when the user says "WDS run VTC workshop" or "WDS create a value trigger chain"'
web_bundle: true
---

# Value Trigger Chain (VTC) Workshop

**Goal:** Create a Value Trigger Chain to connect business goals, user needs, and driving forces

**Your Role:** Strategic facilitator helping create or select VTC based on available context (Trigger Map or from scratch)

---

## WORKFLOW ARCHITECTURE

This uses **step-file architecture** with **routing logic**:

### Core Principles

- **Context-Based Routing**: Selection (if Trigger Map exists) or Creation (from scratch)
- **Strategic Foundation**: VTC connects business goals → solution → user → driving forces → awareness
- **Flexibility**: Can be created early (Product Pitch) or scenario-specific
- **YAML Output**: Structured format for reuse across project

### Critical Rules

- 🎯 **ALWAYS** determine context first (Trigger Map exists?)
- 🔀 **ALWAYS** route to appropriate workshop based on context
- 📊 **ALWAYS** output YAML format
- 🎯 **ALWAYS** capture 2-5 driving forces (positive and negative)
- 📍 **ALWAYS** define customer awareness journey (start → end)

---

## WHEN TO USE

Use this workflow when:
- ✅ Creating Product Pitch (need primary VTC)
- ✅ Defining new scenario (need scenario-specific VTC)
- ✅ Need strategic clarity before design
- ✅ Want to connect business goals to user needs

Skip this workflow when:
- ❌ VTC already exists for this context
- ❌ No strategic planning needed (pure visual design)
- ❌ Working from existing detailed requirements

---

## ROUTING DECISION

**First Question:** "Do you have a completed Trigger Map?"

### Route A: VTC Selection Workshop
**IF YES** - Trigger Map exists

**Use when:**
- Trigger Map is completed
- Want to extract VTC from existing strategic work
- Need consistency with Trigger Map
- Multiple scenarios need VTCs

**Benefits:**
- Leverage existing research
- Maintain consistency
- Faster (select vs. imagine)

**Steps folder:** `steps-c/` (step-01b through step-07b)

---

### Route B: VTC Creation Workshop
**IF NO** - No Trigger Map yet

**Use when:**
- No Trigger Map available
- Early stage (Product Pitch)
- Quick project needing lightweight approach
- Standalone scenario/prototype

**Benefits:**
- Get started immediately
- No Trigger Map overhead
- Sufficient for simple projects

**Steps folder:** `steps-c/` (step-01a through step-07a)

---

## CONTEXT TO PROVIDE

Load and read full config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `user_name`, `communication_language`, `document_output_language`
- `roadmap_product_brief_dir`, `current_outline_scenarios_dir`

When routing to either workshop, gather:

**Project Context:**
- Project name
- Current phase (Pitch or Scenario Definition)
- Purpose of this VTC (what will it be used for?)

**For Selection Workshop (if Trigger Map exists):**
- Path to Trigger Map document
- Number of business goals mapped
- Number of users/personas mapped
- Current scenario being defined (if applicable)

**For Creation Workshop (if no map):**
- Brief project description
- Who is the primary user? (if known)
- What problem are we solving? (if known)

---

## AGENT INSTRUCTIONS

1. Ask: "Do you have a completed Trigger Map?"
2. Based on answer, route to appropriate workshop
3. Provide context information to that workshop
4. Run the selected workshop
5. Save resulting VTC to appropriate location
6. Confirm completion with user

**Example Dialog:**

```
Agent: "I'll help you create a Value Trigger Chain for [context].
        Do you have a completed Trigger Map for this project?"

User: "No, not yet."

Agent: "I'll guide you through creating a VTC from scratch.
        This will take about 30 minutes. Let's start with your
        business goal..."

[Proceeds to Creation Workshop]
```

---

## FIRST STEP EXECUTION

**After routing decision:**

**IF Selection Workshop:**
Load, read and execute `steps-c/step-01b-load-trigger-map.md`

**IF Creation Workshop:**
Load, read and execute `steps-c/step-01a-define-business-goal.md`

**Template:** `../templates/vtc-template.yaml`

---

## OUTPUT

**Completed VTC (YAML format):**

```yaml
businessGoal: [What business wants to achieve]
solution: [How we help user achieve their goal]
user: [Who we're helping]
drivingForces:
  positive:
    - [What they want/hope for]
    - [Another positive driver]
  negative:
    - [What they fear/avoid]
    - [Another negative driver]
customerAwareness:
  start: [Where they are now]
  end: [Where they need to be]
```

**Destination:**
- Product Pitch: `{roadmap_product_brief_dir}/vtc-primary.yaml`
- Scenario: `{current_outline_scenarios_dir}/[scenario-name]/vtc.yaml`

---

## EXAMPLE USE CASES

### Use Case 1: Product Pitch (No Trigger Map)
→ Route to Creation Workshop
→ Create primary VTC from scratch
→ Save to `{roadmap_product_brief_dir}/vtc-primary.yaml`

### Use Case 2: Scenario Definition (Trigger Map Exists)
→ Route to Selection Workshop
→ Select business goal + user from Trigger Map
→ Customize driving forces for scenario
→ Save to `{current_outline_scenarios_dir}/[scenario]/vtc.yaml`

### Use Case 3: Multiple Scenarios
→ Route to Selection Workshop for each
→ Create variant VTCs from same Trigger Map
→ Maintain consistency across scenarios

---

## ALPHA STATUS

**This workshop is in ALPHA** - feedback needed.

Please document:
- Where you got stuck
- What took longer than estimated
- What needs clarification
- What's missing

Add feedback to VTC file notes section.
