---
name: 'step-01-understand'
description: 'Analyze the requirement delta between current state and what user wants to build'

templateFile: '../tech-spec-template.md'
specDir: '{implementation_artifacts}'
---

# Step 1: Analyze Requirement Delta

**Progress: Step 1 of 4** - Next: Deep Investigation

## RULES:

- MUST NOT skip steps.
- MUST NOT optimize sequence.
- MUST follow exact instructions.
- MUST NOT look ahead to future steps.
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`

## CONTEXT:

- Variables from `workflow.md` are available in memory.
- Focus: Define the technical requirement delta and scope.
- Investigation: Perform surface-level code scans ONLY to verify the delta. Reserve deep dives into implementation consequences for Step 2.
- Objective: Establish a verifiable delta between current state and target state.

## SEQUENCE OF INSTRUCTIONS

### 0. Check for Drafts in Progress

a) **Before anything else, scan `{specDir}` for in-progress drafts:**

- Glob `{specDir}/spec-*.md` and read the frontmatter of each match.
- A file is an in-progress draft when its frontmatter has `status: 'draft'` AND `stepsCompleted` is set with at least one entry.

b) **IF ONE OR MORE DRAFT SPECS EXIST:**

1. For each draft, extract: `title`, `slug`, `stepsCompleted`, and the file path.
2. Calculate progress per draft: `lastStep = max(stepsCompleted)`.
3. Present to user:

```
{user_name}, one or more quick-spec drafts in progress were found:

  [1] {title-1} - Step {lastStep-1} of 4 complete  ({specDir}/spec-{slug-1}.md)
  [2] {title-2} - Step {lastStep-2} of 4 complete  ({specDir}/spec-{slug-2}.md)
  ...

Select one to resume, or start fresh:

[1..N] Resume that draft
[N] No, archive none — start something new
[A-k] Archive draft k and continue browsing
```

4. **HALT and wait for user selection.**

a) **Menu Handling:**

- **[1..N] Resume existing:**
  - Set `{specFile}` to the chosen file's path.
  - Jump directly to the appropriate step based on the chosen file's `stepsCompleted`:
    - `[1]` → Read fully and follow: `{project-root}/_bmad/compass/4-implementation/bmad-compass-quick-spec/steps/step-02-investigate.md` (Step 2)
    - `[1, 2]` → Read fully and follow: `{project-root}/_bmad/compass/4-implementation/bmad-compass-quick-spec/steps/step-03-generate.md` (Step 3)
    - `[1, 2, 3]` → Read fully and follow: `{project-root}/_bmad/compass/4-implementation/bmad-compass-quick-spec/steps/step-04-review.md` (Step 4)
- **[A-k] Archive draft k:**
  - Rename `{specDir}/spec-{slug-k}.md` to `{specDir}/spec-{slug-k}-archived-{date}.md` and redisplay the menu.
- **[N] Start fresh:**
  - Proceed to section 1 below. Existing drafts remain untouched.

### 1. Greet and Ask for Initial Request

a) **Greet the user briefly:**

"{user_name}, what are we building today?"

b) **Get their initial description.** Don't ask detailed questions yet - just understand enough to know where to look.

### 2. Quick Orient Scan

a) **Before asking detailed questions, do a rapid scan to understand the landscape:**

b) **Check for existing context docs:**

- Check `{current_architecture_dir}`, `{current_prd_dir}`, `{current_epics_dir}`, and `{current_research_dir}` for active planning documents
- Check for `**/project-context.md` - if it exists, skim for patterns and conventions
- Check for any existing stories or specs related to user's request

c) **If user mentioned specific code/features, do a quick scan:**

- Search for relevant files/classes/functions they mentioned
- Skim the structure (don't deep-dive yet - that's Step 2)
- Note: tech stack, obvious patterns, file locations

d) **Build mental model:**

- What's the likely landscape for this feature?
- What's the likely scope based on what you found?
- What questions do you NOW have, informed by the code?

**This scan should take < 30 seconds. Just enough to ask smart questions.**

### 3. Ask Informed Questions

a) **Now ask clarifying questions - but make them INFORMED by what you found:**

Instead of generic questions like "What's the scope?", ask specific ones like:
- "`AuthService` handles validation in the controller — should the new field follow that pattern or move it to a dedicated validator?"
- "`NavigationSidebar` component uses local state for the 'collapsed' toggle — should we stick with that or move it to the global store?"
- "The epics doc mentions X - is this related?"

**Adapt to {user_skill_level}.** Technical users want technical questions. Non-technical users need translation.

b) **If no existing code is found:**

- Ask about intended architecture, patterns, constraints
- Ask what similar systems they'd like to emulate

### 4. Capture Core Understanding

a) **From the conversation, extract and confirm:**

- **Title**: A clear, concise name for this work
- **Slug**: Kebab-case identifier derived from the title using the rules below:
  - If the intent references a tracking identifier (story `X.Y`, `#N`, `issue N`, `gh-N`), lead the slug with it — `3-2-digest-delivery`, `gh-47-fix-auth`.
  - Otherwise slugify the title to lowercase-hyphen form: strip apostrophes, replace other non-alphanumeric runs with a single hyphen, and drop leading stopwords (`the`, `a`, `an`, `and`, etc.).
  - Before committing the slug, glob `{specDir}/spec-*.md`. If `{specDir}/spec-{slug}.md` already exists, append `-2`, `-3`, ... until the filename is unique.
  - These rules mirror `tools/quick-dev-scan.js:deriveSpecSlug` — consult it as the source of truth for conflict semantics.
- **Problem Statement**: What problem are we solving?
- **Solution**: High-level approach (1-2 sentences)
- **In Scope**: What's included
- **Out of Scope**: What's explicitly NOT included

b) **Ask the user to confirm the captured understanding before proceeding.** Set `{specFile}` = `{specDir}/spec-{slug}.md`.

### 5. Initialize Spec File

a) **Create the tech-spec file at `{specFile}`:**

1. Copy template from `{templateFile}`
2. Write to `{specFile}`
3. Update frontmatter with captured values:
   ```yaml
   ---
   title: '{title}'
   slug: '{slug}'
   created: '{date}'
   status: 'draft'
   stepsCompleted: [1]
   tech_stack: []
   files_to_modify: []
   code_patterns: []
   test_patterns: []
   ---
   ```
4. Fill in Overview section with Problem Statement, Solution, and Scope
5. Fill in Context for Development section with any technical preferences or constraints gathered during informed discovery.
6. Write the file

b) **Report to user:**

"Created: `{specFile}`

**Captured:**

- Title: {title}
- Problem: {problem_statement_summary}
- Scope: {scope_summary}"

### 6. Present Checkpoint Menu

a) **Display menu:**

Display: "**Select:** [A] Advanced Elicitation [P] Party Mode [C] Continue to Deep Investigation (Step 2 of 4)"

b) **HALT and wait for user selection.**

#### Menu Handling Logic:

- IF A: Read fully and follow: `{advanced_elicitation}` with current tech-spec content, process enhanced insights, ask user "Accept improvements? (y/n)", if yes update `{specFile}` then redisplay menu, if no keep original then redisplay menu
- IF P: Read fully and follow: `{party_mode_exec}` with current tech-spec content, process collaborative insights, ask user "Accept changes? (y/n)", if yes update `{specFile}` then redisplay menu, if no keep original then redisplay menu
- IF C: Verify `{specFile}` has `stepsCompleted: [1]`, then read fully and follow: `{project-root}/_bmad/compass/4-implementation/bmad-compass-quick-spec/steps/step-02-investigate.md`
- IF Any other comments or queries: respond helpfully then redisplay menu

#### EXECUTION RULES:

- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed to next step when user selects 'C'
- After A or P execution, return to this menu

---

## REQUIRED OUTPUTS:

- MUST initialize `{specFile}` with captured metadata.

## VERIFICATION CHECKLIST:

- [ ] Draft scan performed FIRST before any greeting.
- [ ] Slug derived per `tools/quick-dev-scan.js:deriveSpecSlug` rules; collisions in `{specDir}/spec-*.md` suffixed `-2`, `-3`, ...
- [ ] `{specFile}` = `{specDir}/spec-{slug}.md` created with correct frontmatter (`status: 'draft'`, `stepsCompleted: [1]`), Overview, and Context for Development.
- [ ] User selected [C] to continue.
