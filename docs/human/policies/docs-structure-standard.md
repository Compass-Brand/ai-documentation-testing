# Documentation Structure Standard

## Purpose

Define a single documentation layout for all company projects.

## Scope

Applies to repository-level documentation organization, naming, and cross-linking for human-facing docs.

## Requirements

### 1. Standard repository documentation tree

Projects MUST use this minimum documentation tree:

```text
project/
├── docs/
│   ├── architecture/
│   │   ├── decisions/
│   │   │   └── README.md
│   │   └── README.md
│   ├── development/
│   │   └── README.md
│   ├── getting-started/
│   │   ├── installation.md
│   │   ├── quickstart.md
│   │   └── README.md
│   ├── guides/
│   │   └── README.md
│   ├── reference/
│   │   └── README.md
│   └── README.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

Rationale: a single predictable structure reduces discovery time for both humans and automation tooling.

Implementation Playbook (Mandatory):

1. Scaffold this tree at project setup.
2. Verify tree presence in docs audits.
3. Add project-specific subfolders under the approved top-level docs folders.

### 2. README at each documentation level

Every docs directory MUST contain a `README.md` that explains purpose and links to child documents.

Rationale: per-directory indexes prevent orphaned docs and make navigation obvious.

Implementation Playbook (Mandatory):

1. Create `README.md` with scope, audience, and child index when adding any docs folder.
2. Update parent `README.md` when adding or removing child docs.
3. Review README indexes during quarterly documentation review.

### 3. Topic folder extensions

Teams MAY add topic subfolders under `architecture/`, `development/`, `guides/`, or `reference/`.
If `docs/brand/` is required for a project, it SHOULD include its own `README.md` and explicit scope.

Rationale: controlled extensibility supports project-specific needs without fragmenting the core structure.

Implementation Playbook (Mandatory):

1. Add topic directories only under approved parent folders.
2. Provide index README and naming rationale for each added topic directory.
3. Remove stale topic directories when content is deprecated.

### 4. File naming and ADR numbering

Documentation file names MUST use lowercase kebab-case.
ADR files MUST use zero-padded sequence numbers, for example `0001-topic.md`.
Ambiguous file names such as `notes.md` and `misc.md` MUST NOT be used.

Rationale: strict naming conventions improve searchability, sorting, and long-term maintainability.

Implementation Playbook (Mandatory):

1. Name files in kebab-case at creation time.
2. Keep ADR numbering monotonic and unique.
3. Rename ambiguous files during cleanup or review.

### 5. Link standards

Internal links MUST use relative paths.
Link text MUST describe destination purpose.
Documents SHOULD cross-link setup, guides, reference, and architecture where relevant.

Rationale: relative links survive repository moves, and descriptive links improve usability and accessibility.

Implementation Playbook (Mandatory):

1. Use relative links for all in-repo navigation.
2. Replace vague link text with purpose-driven labels.
3. Validate links as part of docs quality checks.

### 6. Asset and diagram placement

Architecture diagrams SHOULD default to Mermaid embedded in markdown.
Static images MUST use descriptive names and SHOULD be stored in `docs/assets/images/`.

Rationale: diagrams-as-code lowers maintenance burden and keeps architecture visuals reviewable in pull requests.

Implementation Playbook (Mandatory):

1. Prefer Mermaid for new diagrams.
2. Store static assets under `docs/assets/images/` unless a local-folder exception is justified.
3. Keep diagram names domain-specific, not generic.

### 7. Monorepo and polyrepo guidance

Monorepos MUST define whether docs ownership is centralized or package-local.
Polyrepos SHOULD keep each repo self-documenting and MAY use a central docs hub for cross-repo architecture.

Rationale: explicit ownership model prevents missing coverage between repository boundaries.

Implementation Playbook (Mandatory):

1. Document docs ownership model in root docs.
2. For monorepos, specify which content lives centrally vs per package.
3. For polyrepos, link each repo docs index from central architecture or overview docs.

### 8. Documentation control-plane extensions

Projects using Compass BMAD documentation workflows MUST also include:

- `docs/human/policies/`
- `docs/human/templates/`
- `docs/human/policies/user-overrides.md`
- `docs/ai/README.md`

These paths are control-plane assets for local documentation governance and AI-facing standards. They are not replacements for the primary reader-facing docs tree.

Rationale: Compass BMAD documentation workflows need a stable project-local place for baseline policies, templates, project overrides, and AI-facing standards without overloading the user-facing docs sections.

Implementation Playbook (Mandatory):

1. Scaffold these control-plane paths when initializing docs through Compass BMAD.
2. Keep baseline policy and template copies aligned to the current framework source.
3. Use `docs/human/policies/user-overrides.md` only for project-specific additions, not for replacing baseline requirements.

## Compliance checks

- ADR numbering is sequential and unique.
- Every docs folder has a `README.md`.
- Internal links are relative and valid.
- Naming conventions pass spot check.
- Ownership model is documented for mono/polyrepo contexts.
- Required tree exists.
- When Compass BMAD docs workflows are installed, `docs/human/` and `docs/ai/README.md` exist and are aligned.

## Exceptions

Exceptions MUST follow `documentation-governance.md`.

## Related

- `../templates/readme-docs-index.md`
- `architecture-standard.md`
- `documentation-governance.md`
- `guides-standard.md`
