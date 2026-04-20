---
name: 'step-01-init'
description: 'Initialize the Architecture workflow by detecting continuation state and setting up the document'

# File References
nextStepFile: './step-02-context.md'
continueStepFile: './step-01b-continue.md'
outputFile: '{current_architecture_dir}/architecture.md'

# Template Reference
architectureTemplate: '../architecture-decision-template.md'
---

# Step 1: Architecture Workflow Initialization

**Progress: Step 1 of 8** - Next: Project Context Analysis

## MANDATORY EXECUTION RULES (READ FIRST):

- 🛑 NEVER generate content without user input
- 📖 CRITICAL: ALWAYS read the complete step file before taking any action - partial understanding leads to incomplete decisions
- 🔄 CRITICAL: When loading next step with 'C', ensure the entire file is read and understood before proceeding
- ✅ ALWAYS treat this as collaborative discovery between architectural peers
- 📋 YOU ARE A FACILITATOR, not a content generator
- 💬 FOCUS on initialization and setup only - don't look ahead to future steps
- 🚪 DETECT existing workflow state and handle continuation properly
- ⚠️ ABSOLUTELY NO TIME ESTIMATES - AI development speed has fundamentally changed
- 🧭 When this workflow is launched from the custom BMM bundle, continue on the local custom step chain only; do not swap to native step files if the custom files exist
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

## EXECUTION PROTOCOLS:

- 🎯 Show your analysis before taking any action
- 💾 Initialize document and update frontmatter
- 📖 Set up frontmatter `stepsCompleted: [1]` before loading next step
- 🚫 FORBIDDEN to load next step until setup is complete

## CONTEXT BOUNDARIES:

- Variables from workflow.md are available in memory
- Previous context = what's in output document + frontmatter
- Don't assume knowledge from other steps
- Input document discovery happens in this step

## YOUR TASK:

Initialize the Architecture workflow by detecting continuation state, discovering input documents, and setting up the document for collaborative architectural decision making.

## INITIALIZATION SEQUENCE:

### 1. Check for Existing Workflow

First, check if the output document already exists:

- Look for existing `{current_architecture_dir}/*architecture*.md`
- If exists, read the complete file(s) including frontmatter
- If not exists, this is a fresh workflow

### 2. Handle Continuation (If Document Exists)

If the document exists and has frontmatter with `stepsCompleted`:

- **STOP here** and load `{project-root}/_bmad/bmm/3-solutioning/bmad-create-architecture/steps/step-01b-continue.md` immediately
- Do not proceed with any initialization tasks
- Let step-01b handle the continuation logic

### 3. Fresh Workflow Setup (If No Document)

If no document exists or no `stepsCompleted` in frontmatter:

#### A. Input Document Discovery

Discover and load context documents using smart discovery. Documents can be in the following locations:
- {planning_root}/roadmap/product-brief/**
- {planning_root}/roadmap/research/**
- {planning_root}/roadmap/brainstorming/**
- {planning_root}/roadmap/strategy/**
- {planning_current}/**
- {output_folder}/**
- {project_knowledge}/**
- docs/**

Also - when searching - documents can be a single markdown file, or a folder with an index and multiple files. For Example, if searching for `*foo*.md` and not found, also search for a folder called *foo*/index.md (which indicates sharded content)

Try to discover the following:
- Product Brief (prefer `{planning_root}/roadmap/product-brief/**/*.md`, including `product-brief-*.md` and sharded `product-brief/index.md`)
- Product Requirements Document (`*prd*.md`)
- UX Design (`*ux-design*.md`) and other
- Research Documents (`*research*.md`)
- Project Documentation (generally multiple documents might be found for this in the `{project_knowledge}` or `docs` folder.)
- Project Context (`**/project-context.md`)

Framework scaffolds do **not** count as substantive project documentation by themselves. Treat baseline docs templates, policies, initialization reports, and control-plane READMEs as scaffold-only unless they contain repo-specific architectural or operational context. If only scaffold files exist, report them as scaffold-only rather than as substantive project docs.

<critical>Confirm what you have found with the user, along with asking if the user wants to provide anything else. Only after this confirmation will you proceed to follow the loading rules</critical>

**Loading Rules:**

- Load confirmed files using targeted reads. Read frontmatter and summary sections first. Load full PRD content (primary input). For other documents (research, brief, UX), read summaries only unless architecture decisions require specific details from them.
- If there is a project context, whatever is relevant should try to be biased in the remainder of this whole workflow process
- For sharded folders, load the index first and reference individual shards on demand
- index.md is a guide to what's relevant whenever available
- Track all successfully loaded files in frontmatter `inputDocuments` array
- Track document counts in frontmatter `documentCounts`
- Track `projectContextHint` in frontmatter as `greenfield` or `brownfield`
- If only scaffold docs are available, prefer loading the minimal repo-specific context such as the PRD, roadmap product brief, roadmap, and phase files instead of bulk-loading framework scaffolds

#### B. Validate Required Inputs

Before proceeding, verify we have the essential inputs:

**PRD Validation:**

- If no PRD found: "Architecture requires a PRD to work from. Please run the PRD workflow first or provide the PRD file path."
- Do NOT proceed without PRD

**Other Input that might exist:**

- UX Spec: "Provides UI/UX architectural requirements"

#### C. Create Initial Document

**Document Setup:**

- Copy the template from `{architectureTemplate}` to `{outputFile}`
- Initialize frontmatter with proper structure including `inputDocuments`, `documentCounts`, and `projectContextHint`.

#### D. Present Initialization Results

**Setup Report to User:**

"I've set up the Architecture workspace for this repo.

**Document Setup:**

- Created: `{outputFile}` from template
- Initialized frontmatter with workflow state

**Input Documents Discovered:**

*Replace each {{variable}} with the actual count from discovery and evaluate each {if}...{else}...{/if} block so the output shows real numbers and the correct branch text.*

- PRD: {{prdCount}} files {if prdCount > 0}✓ loaded{else}(none found - REQUIRED){/if}
- Product briefs: {{briefCount}} files {if briefCount > 0}✓ loaded{else}(none found){/if}
- UX Design: {{uxCount}} files {if uxCount > 0}✓ loaded{else}(none found){/if}
- Research: {{researchCount}} files {if researchCount > 0}✓ loaded{else}(none found){/if}
- Project docs: {{projectDocsCount}} substantive files {if projectDocsCount > 0}✓ loaded{else}(none found or scaffold-only){/if}

**Files loaded:** {list of specific file names or "No additional documents found"}

**Project context:** {{projectContextHint}}

{if projectContextHint == "brownfield"}
📋 **Note:** This is a **brownfield project**. Existing substantive project documentation has been loaded, so architectural decisions should account for changes to an existing system.
{else}
📋 **Note:** This is a **greenfield project**. Scaffold-only docs do not change that classification. Architectural decisions should be informed by the product brief and the repo's stated purpose.
{/if}

Do you have any other documents you'd like me to include, or shall we continue to the next step?"

### 4. Present MENU OPTIONS

Display menu after setup report:

"[C] Continue - Save this and move to Project Context Analysis (Step 2 of 8)"

#### Menu Handling Logic:

- IF C: Update output file frontmatter, adding this step name to the end of the list of stepsCompleted, then read fully and follow: {nextStepFile}
- IF user provides additional files: Load them, update inputDocuments and documentCounts, redisplay report
- IF user asks questions: Answer and redisplay menu

#### EXECUTION RULES:

- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed to next step when user selects 'C'

## CRITICAL STEP COMPLETION NOTE

ONLY WHEN [C continue option] is selected and [frontmatter properly updated with this step added to stepsCompleted and documentCounts], will you then read fully and follow: `{nextStepFile}` to begin project context analysis.

---

## 🚨 SYSTEM SUCCESS/FAILURE METRICS

### ✅ SUCCESS:

- Existing workflow detected and properly handed off to step-01b
- Fresh workflow initialized with template and proper frontmatter
- Input documents discovered and loaded using sharded-first logic
- All discovered files tracked in frontmatter `inputDocuments`
- PRD requirement validated and communicated
- User clearly informed of brownfield vs greenfield status
- Menu presented and user input handled correctly
- Frontmatter updated with this step name added to stepsCompleted before proceeding

### ❌ SYSTEM FAILURE:

- Proceeding with fresh initialization when existing workflow exists
- Not updating frontmatter with discovered input documents
- **Not storing document counts in frontmatter**
- Creating document without proper template structure
- Not checking sharded folders first before whole files
- Not reporting discovered documents to user clearly
- Proceeding without user selecting 'C' (Continue)
- Proceeding without validating PRD requirement
- Using config `project_name` as repo identity instead of deriving from `{project-root}`

**Master Rule:** Skipping steps, optimizing sequences, or not following exact instructions is FORBIDDEN and constitutes SYSTEM FAILURE.
