# Documentation Style Standard

## Purpose

Define writing, formatting, and accessibility standards for human-facing docs.

## Scope

Applies to all markdown documentation in project roots and `docs/` directories.

## Requirements

### 1. Voice and clarity requirements

Documents MUST use direct and plain language.
Writers SHOULD prefer active voice and concise sentences.
Audience context MUST be explicit when content is specialized.

Rationale: readers need fast comprehension, and vague prose increases support burden and implementation mistakes.

Implementation Playbook (Mandatory):

1. State audience and intent near the top of each document.
2. Rewrite passive phrasing where ownership and action matter.
3. Replace abstract wording with concrete examples or commands.

### 2. Heading structure requirements

Each document MUST contain exactly one H1 title.
Heading levels MUST be sequential (`H2` under `H1`, `H3` under `H2`).
Bold text MUST NOT be used as a heading substitute.

Rationale: consistent heading semantics improve navigation, accessibility, and automated parsing.

Implementation Playbook (Mandatory):

1. Validate heading depth before merge.
2. Convert ad-hoc bold pseudo-headers into real headings.
3. Ensure section names describe content accurately.

### 3. Code and command requirements

Fenced code blocks MUST include language identifiers.
Commands MUST be copy-pasteable unless explicitly marked illustrative.
Paths, commands, environment variables, and identifiers SHOULD use inline code formatting.

Rationale: runnable and clearly marked examples reduce ambiguity and increase adoption speed.

Implementation Playbook (Mandatory):

1. Label every code block with a language.
2. Test command snippets where possible.
3. Mark pseudo examples explicitly when they cannot be executed directly.

### 4. Link quality requirements

Link text MUST be descriptive.
Phrases such as "click here" MUST NOT be used as standalone link text.
Internal links MUST be relative and maintained when files move.

Rationale: descriptive linking improves accessibility and keeps docs stable across branch and repository changes.

Implementation Playbook (Mandatory):

1. Replace generic link text with destination-specific labels.
2. Update links when moving or renaming files.
3. Run link validation before merge.

### 5. Accessibility requirements

Images MUST include meaningful alt text.
Tables SHOULD be used for comparative data, not for layout.
Long prose sections SHOULD be broken into headings, bullets, or tables when readability suffers.

Rationale: accessible formatting ensures broader usability and easier scanning for all readers.

Implementation Playbook (Mandatory):

1. Provide alt text that explains image intent.
2. Use lists and tables only when they improve comprehension.
3. Split dense sections into smaller semantic chunks.

### 6. Terminology consistency requirements

Core domain terms MUST remain consistent across all docs in a repository.
Acronyms MUST be expanded on first use unless universally established.

Rationale: terminology drift creates hidden contradictions even when instructions appear correct.

Implementation Playbook (Mandatory):

1. Maintain a terms list in project documentation.
2. Normalize variant terms during review.
3. Expand acronyms on first mention in each document.

### 7. Common mistakes to prevent

The following patterns MUST NOT appear in committed documentation:

- contradictory setup instructions,
- jargon without definition,
- missing install/setup instructions,
- missing runnable examples,
- outdated screenshots without context or date,
- unlabeled code fences,
- unresolved placeholders (`TODO`, `TBD`, `coming soon`).

Rationale: these patterns are the highest-frequency causes of confused onboarding and stale docs.

Implementation Playbook (Mandatory):

1. Check setup and usage sections for actionable steps.
2. Search for placeholders and remove them.
3. Validate that screenshots are current or explicitly dated.
4. Define jargon at first mention.

## Compliance checks

- Accessibility checks pass for images and structure.
- All fenced blocks include language.
- Link text is descriptive and links resolve.
- No placeholder tokens remain.
- One H1 and sequential heading structure.
- Terminology remains consistent across related docs.

## Exceptions

Exceptions MUST follow `documentation-governance.md`.

## Related

- `../templates/guide-howto.md`
- `../templates/guide-tutorial.md`
- `docs-structure-standard.md`
- `guides-standard.md`
