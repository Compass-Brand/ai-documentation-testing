# Workflow: Advanced Elicitation

## Purpose
Enhance a draft section or recent output by applying targeted elicitation techniques iteratively until the user accepts and proceeds.

## Mandatory Execution Rules
- Execute all steps in order.
- Always halt for user input when a selection is requested.
- Keep output in the active communication style and configured language.
- Apply enhancements to the current working content only.
- Re-offer options after each method execution until user selects `x`.

## Integration Contract
When invoked from another workflow:
1. Receive the current draft content section.
2. Apply selected elicitation methods iteratively.
3. Ask whether changes should be applied (`y/n/other`).
4. Return accepted enhanced content to caller when user selects `x`.

## Flow
### 1. Load Method Registry and Context
- Load and read:
- `./methods.csv`
- `{project-root}/_bmad/_config/agent-manifest.csv`
- Understand CSV fields:
- `category`
- `method_name`
- `description`
- `output_pattern`
- Analyze context:
- content type.
- complexity.
- stakeholder needs.
- risk level.
- creative potential.
- Select 5 best-fit methods for initial menu.

### 2. Present Menu and Handle Responses
Display:
```text
Advanced Elicitation Options (If you launched Party Mode, they may participate)
Choose a number (1-5), [r] Reshuffle, [a] List All, or [x] Proceed:
1. [Method Name]
2. [Method Name]
3. [Method Name]
4. [Method Name]
5. [Method Name]
r. Reshuffle with 5 new options
a. List all methods with descriptions
x. Proceed / No Further Actions
```

#### Response Handling
- `1-5`:
- execute selected method using CSV description.
- adapt complexity/output to context.
- display improved content.
- ask whether to apply changes (`y/n/other`) and halt for reply.
- if `y`, keep changes.
- if `n`, discard proposed changes.
- if other, follow user instruction as best possible.
- then re-display menu.
- `r`:
- generate 5 new diverse methods and re-display menu.
- `a`:
- show compact table of all methods with descriptions.
- allow method selection by number/name.
- execute like `1-5`.
- `x`:
- finalize elicitation session.
- return accepted enhanced content to caller.
- `direct feedback`:
- apply requested adjustments and re-display menu.
- `multiple numbers`:
- run methods in sequence on current content, then re-display menu.

### 3. Execution Guidelines
- Treat `output_pattern` as a flexible guide, not rigid template.
- Keep suggestions actionable and context-specific.
- Identify personas/viewpoints where helpful, including party participants if present.
- Each selected method should:
- apply to latest accepted content state.
- show what improved.
- loop back for further selection until `x`.
