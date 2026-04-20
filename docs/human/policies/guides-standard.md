# Guides Standard

## Purpose

Define requirements for tutorials, how-to guides, reference pages, and explanation pages.

## Scope

Applies to documents under `docs/guides/`, `docs/reference/`, and supporting explanation content.

## Requirements

### 1. Diataxis mode separation

Each guide document MUST use one primary mode:

- explanation (understanding-oriented),
- how-to (task-oriented),
- reference (lookup-oriented),
- tutorial (learning-oriented).

Guide documents MUST NOT mix tutorial flow with broad reference tables in the same page.

Rationale: mode separation avoids cognitive overload and makes each document immediately useful for its intended task.

Implementation Playbook (Mandatory):

1. Select mode before drafting.
2. Remove sections that do not fit selected mode.
3. Split mixed-content documents into multiple pages when needed.

### 2. Guide mode selection process

Authors MUST determine guide type by reader intent:

- learn-by-doing -> tutorial,
- look up exact behavior -> reference,
- perform known task -> how-to,
- understand why/tradeoffs -> explanation.

Rationale: intent-first classification prevents structure drift and improves findability.

Implementation Playbook (Mandatory):

1. Record intended reader outcome at draft start.
2. Map outcome to one mode using the matrix above.
3. Add cross-links to related modes as needed.

### 3. Tutorial requirements

Tutorials MUST include:

- end-to-end verification,
- expected results after each step,
- learning outcomes,
- next steps,
- ordered step-by-step instructions,
- prerequisites.

Rationale: tutorials succeed only when a reader can complete them from start to finish without hidden assumptions.

Implementation Playbook (Mandatory):

1. Test tutorial from a clean environment.
2. Add explicit expected output checkpoints.
3. Include at least one troubleshooting case for likely failure.

### 4. How-to requirements

How-to guides MUST include:

- a single concrete goal,
- prerequisites,
- procedure steps,
- troubleshooting for common failures,
- verification section.

Rationale: task-driven docs must be scannable and verifiable for time-constrained readers.

Implementation Playbook (Mandatory):

1. Keep one goal per guide.
2. Place prerequisites near the top.
3. Ensure verification confirms final state, not just command execution.

### 5. Reference requirements

Reference docs MUST remain concise and exhaustive within scope.
Reference entries MUST define behavior, accepted inputs, defaults, and constraints.
Reference docs SHOULD include runnable examples for critical entries.

Rationale: reference material is used as a source of truth; omissions and ambiguity undermine trust quickly.

Implementation Playbook (Mandatory):

1. Use consistent heading structure per entry.
2. Include default values and allowed ranges/types.
3. Add examples for high-impact or error-prone parameters.

### 6. Explanation requirements

Explanation docs MUST focus on why, tradeoffs, and design rationale.
Explanation docs MUST link to practical how-to or reference documents when operational use is implied.

Rationale: conceptual docs are valuable only when they connect rationale to practical execution.

Implementation Playbook (Mandatory):

1. Capture decision rationale and alternatives.
2. Avoid implementation step lists unless linked to a separate how-to.
3. Link to concrete operational docs.

### 7. Mandatory modern practices

The following practices are mandatory in guide authoring:

- Docs-as-code MUST be used (versioned markdown, pull request review).
- Drift prevention MUST be enforced by updating docs alongside behavior changes.
- Progressive disclosure MUST be used (simple path first, advanced depth later).
- Runnable examples MUST be preferred over pseudo examples.
- Time to First Hello World (TTFHW) MUST be minimized in onboarding docs.

Rationale: these practices directly reduce onboarding time, rework, and stale documentation failure modes.

Implementation Playbook (Mandatory):

1. Track the shortest path to a successful first result in getting-started docs.
2. Keep docs in repository and review through pull requests.
3. Validate examples during change review.
4. Structure guides with base flow first and advanced sections clearly separated.
5. Couple docs updates with affected code/config changes.

### 8. Documentation-driven development

For new user-facing workflows, teams MUST draft guide structure before implementation begins.

Rationale: pre-writing the workflow reveals missing requirements and reduces design ambiguity earlier in the lifecycle.

Implementation Playbook (Mandatory):

1. Draft high-level tutorial or how-to outline before coding major features.
2. Validate outline against product/engineering intent.
3. Update final guide during implementation, not after release.

### 9. Cross-linking requirements

Explanation pages SHOULD link to executable guides.
How-to guides SHOULD link to explanation pages for rationale.
Tutorials SHOULD link to reference pages for detail.

Rationale: cross-linking creates an intentional documentation graph rather than isolated pages.

Implementation Playbook (Mandatory):

1. Add related links section to each guide.
2. Verify cross-links on every structural doc change.
3. Remove stale links during quarterly review.

## Compliance checks

- Cross-links are present and valid across doc types.
- Each guide has a single mode.
- Mode selection rationale is clear from document structure.
- Modern practices are visible in structure and content.
- Tutorial and how-to pages include verification.

## Exceptions

Exceptions MUST follow `documentation-governance.md`.

## Related

- `../templates/guide-howto.md`
- `../templates/guide-tutorial.md`
- `documentation-governance.md`
- `style-standard.md`
