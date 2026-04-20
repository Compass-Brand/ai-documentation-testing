# Step 2: Project Context Analysis

## MANDATORY EXECUTION RULES (READ FIRST):

- 🛑 NEVER generate content without user input

- 📖 CRITICAL: ALWAYS read the complete step file before taking any action - partial understanding leads to incomplete decisions
- 🔄 CRITICAL: When loading next step with 'C', ensure the entire file is read and understood before proceeding
- ✅ ALWAYS treat this as collaborative discovery between architectural peers
- 📋 YOU ARE A FACILITATOR, not a content generator
- 💬 FOCUS on understanding project scope and requirements for architecture
- 🎯 ANALYZE loaded documents, don't assume or generate requirements
- ⚠️ ABSOLUTELY NO TIME ESTIMATES - AI development speed has fundamentally changed
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

## EXECUTION PROTOCOLS:

- 🎯 Show your analysis before taking any action
- ⚠️ Present A/P/C menu after generating project context analysis
- 💾 ONLY save when user chooses C (Continue)
- 📖 Update frontmatter `stepsCompleted: [1, 2]` before loading next step
- 🚫 FORBIDDEN to load next step until C is selected

## COLLABORATION MENUS (A/P/C):

This step will generate content and present choices:

- **A (Advanced Elicitation)**: Use discovery protocols to develop deeper insights about project context and architectural implications
- **P (Party Mode)**: Bring multiple perspectives to analyze project requirements from different architectural angles
- **C (Continue)**: Save the content to the document and proceed to next step

## PROTOCOL INTEGRATION:

- When 'A' selected: Read fully and follow: {project-root}/_bmad/core/bmad-advanced-elicitation/workflow.xml
- When 'P' selected: Read fully and follow: {project-root}/_bmad/core/bmad-party-mode/workflow.md
- PROTOCOLS always return to display this step's A/P/C menu after the A or P have completed
- User accepts/rejects protocol changes before proceeding

## CONTEXT BOUNDARIES:

- Current document and frontmatter from step 1 are available
- Input documents already loaded are in memory (PRD, epics, UX spec, etc.)
- Focus on architectural implications of requirements
- No technology decisions yet - pure analysis phase

## SCOPE-AWARE PRD GUARD:

When a PRD is already available and the scope is narrow, use the PRD as the primary source for requirements and context. Skip comprehensive re-discovery and focus on any gaps specifically needed for architecture decisions. Do not re-examine requirements, NFRs, or constraints that are already settled in the PRD unless the user asks to revisit them.

## YOUR TASK:

Fully read and Analyze the loaded project documents to understand architectural scope, requirements, and constraints before beginning decision making. When a PRD has already been loaded, treat it as the source of truth and focus analysis on architectural implications rather than re-discovering requirements.

## CONTEXT ANALYSIS SEQUENCE:

### 1. Review Project Requirements

**When PRD is available (primary path):**

The PRD has already captured functional and non-functional requirements. Do NOT re-extract or re-analyze them. Instead, focus on architectural implications:

- Reference the PRD's requirement summaries for architectural context
- **PRESERVE UPSTREAM GROUPING:** When summarizing functional requirements from the PRD, preserve the upstream requirement grouping structure (section headings and category boundaries) exactly as defined in the PRD. Do not collapse, merge, or rename FR categories unless the user explicitly requests regrouping. The architecture must trace back to the PRD's requirement structure so that downstream artifacts maintain clear provenance.
- Identify which requirements drive key architecture decisions (e.g., real-time needs imply WebSocket infrastructure, multi-tenancy implies data isolation patterns)
- Note constraints or quality attributes that affect system design (performance targets, compliance mandates, scalability expectations)
- Identify trade-offs that need resolution during architecture (e.g., consistency vs availability, build vs buy)
- Flag any gaps where the PRD is silent but architecture needs a decision

**When NO PRD is available (fallback):**

- Extract and analyze Functional Requirements (FRs) from available documents
- Identify Non-Functional Requirements (NFRs) like performance, security, compliance
- Note any technical constraints or dependencies mentioned
- Count and categorize requirements to understand project scale

**From Epics/Stories (if available):**

- Map epic structure and user stories to architectural components
- Extract acceptance criteria for technical implications
- Identify cross-cutting concerns that span multiple epics

**From UX Design (if available):**

- Extract architectural implications from UX requirements:
  - Component complexity (simple forms vs rich interactions)
  - Real-time update needs (live data, collaborative features)
  - Platform-specific UI requirements
  - Accessibility standards (WCAG compliance level)
  - Offline capability requirements
  - Performance expectations (load times, interaction responsiveness)

### 2. Project Scale Assessment

Calculate and present project complexity:

**Complexity Indicators:**

- Real-time features requirements
- Multi-tenancy needs
- Regulatory compliance requirements
- Integration complexity
- User interaction complexity
- Data complexity and volume

### 3. Reflect Understanding

Present your analysis back to user for validation:

"I'm reviewing the project documentation for this repo.

{if_epics_loaded}I see {{epic_count}} epics with {{story_count}} total stories.{/if_epics_loaded}
{if_no_epics}I found {{fr_count}} functional requirements organized into {{fr_category_list}}.{/if_no_epics}
{if_ux_loaded}I also found your UX specification which defines the user experience requirements.{/if_ux_loaded}

**Key architectural aspects I notice:**

- [Summarize core functionality from FRs, preserving the PRD's original category groupings]
- [Note critical NFRs that will shape architecture]
- {if_ux_loaded}[Note UX complexity and technical requirements]{/if_ux_loaded}
- [Identify unique technical challenges or constraints]
- [Highlight any regulatory or compliance requirements]

**Scale indicators:**

- Project complexity appears to be: [low/medium/high/enterprise]
- Primary technical domain: [web/mobile/api/backend/full-stack/etc]
- Cross-cutting concerns identified: [list major ones]

This analysis will help me guide you through the architectural decisions needed to ensure AI agents implement this consistently.

Does this match your understanding of the project scope and requirements?"

### 4. Generate Project Context Content

Prepare the content to append to the document:

#### Content Structure:

```markdown
## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
{{Preserve the PRD's original FR category groupings as sub-headings. For each category, provide the architectural analysis. Do NOT merge, collapse, or rename categories from the PRD.}}

**Non-Functional Requirements:**
{{NFRs that will drive architectural decisions}}

**Scale & Complexity:**
{{project_scale_assessment}}

- Primary domain: {{technical_domain}}
- Complexity level: {{complexity_level}}
- Estimated architectural components: {{component_count}}

### Technical Constraints & Dependencies

{{known_constraints_dependencies}}

### Cross-Cutting Concerns Identified

{{concerns_that_will_affect_multiple_components}}
```

### 5. Present Content and Menu

Show the generated content and present choices:

"I've drafted the Project Context Analysis based on your requirements. This sets the foundation for our architectural decisions.

**Here's what I'll add to the document:**

[Show the complete markdown content from step 4]

**What would you like to do?**
[A] Advanced Elicitation - Let's dive deeper into architectural implications
[P] Party Mode - Bring different perspectives to analyze requirements
[C] Continue - Save this analysis and begin architectural decisions"

### 6. Handle Menu Selection

#### If 'A' (Advanced Elicitation):

- Read fully and follow: {project-root}/_bmad/core/bmad-advanced-elicitation/workflow.xml with the current context analysis
- Process the enhanced architectural insights that come back
- Ask user: "Accept these enhancements to the project context analysis? (y/n)"
- If yes: Update content with improvements, then return to A/P/C menu
- If no: Keep original content, then return to A/P/C menu

#### If 'P' (Party Mode):

- Read fully and follow: {project-root}/_bmad/core/bmad-party-mode/workflow.md with the current project context
- Process the collaborative improvements to architectural understanding
- Ask user: "Accept these changes to the project context analysis? (y/n)"
- If yes: Update content with improvements, then return to A/P/C menu
- If no: Keep original content, then return to A/P/C menu

#### If 'C' (Continue):

- Append the final content to `{current_architecture_dir}/architecture.md`
- Update frontmatter: `stepsCompleted: [1, 2]`
- Load `{project-root}/_bmad/bmm/3-solutioning/bmad-create-architecture/steps/step-03-starter.md`

## APPEND TO DOCUMENT:

When user selects 'C', append the content directly to the document using the structure from step 4.

## SUCCESS METRICS:

✅ All input documents thoroughly analyzed for architectural implications
✅ Project scope and complexity clearly assessed and validated
✅ Technical constraints and dependencies identified
✅ Cross-cutting concerns mapped for architectural planning
✅ User confirmation of project understanding
✅ A/P/C menu presented and handled correctly
✅ Content properly appended to document when C selected

## FAILURE MODES:

❌ Skimming documents without deep architectural analysis
❌ Collapsing, merging, or renaming PRD functional requirement categories without explicit user request
❌ Missing or misinterpreting critical NFRs
❌ Not validating project understanding with user
❌ Underestimating complexity indicators
❌ Generating content without real analysis of loaded documents
❌ Not presenting A/P/C menu after content generation

❌ **CRITICAL**: Reading only partial step file - leads to incomplete understanding and poor decisions
❌ **CRITICAL**: Proceeding with 'C' without fully reading and understanding the next step file
❌ **CRITICAL**: Making decisions without complete understanding of step requirements and protocols

## NEXT STEP:

After user selects 'C' and content is saved to document, load `{project-root}/_bmad/bmm/3-solutioning/bmad-create-architecture/steps/step-03-starter.md` to evaluate starter template options.

Remember: Do NOT proceed to step-03 until user explicitly selects 'C' from the A/P/C menu and content is saved!
