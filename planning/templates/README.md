# Planning Templates

These templates are the starter artifacts for the roadmap-driven planning framework.

## Template Groups

- `roadmap/`: project-level, cross-phase artifacts
- `phase/`: active-phase artifacts
- `orchestration/`: workspace and parent-repo routing/control artifacts
- `implementation/`: reuse, readiness, and closeout support artifacts
- `oversight/`: risk and assumption register templates for advisory tracking

## Usage Rules

- copy templates into the matching `planning/` lane
- keep machine state in yaml templates and human summaries in markdown templates
- update templates only when the framework contract changes
- once copied into `planning/`, the live framework files become authoritative
- do not edit template files to reflect live phase state; update the instantiated framework artifacts instead
- templates may include optional sections (e.g., oversight registers, storytelling lanes) that are not mandated by `documentation-governance.md`; omit sections that do not apply to the current project scope
