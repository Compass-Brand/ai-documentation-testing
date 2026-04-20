# Sprint Planning Validation Checklist

## Core Validation

### Complete Coverage Check

- [ ] Every epic found in the epics document set (`epics.md`, `bmm-epics.md`, or sharded `epic-*.md`) appears in sprint-status.yaml
- [ ] Every story found in the epics document set appears in sprint-status.yaml
- [ ] Every epic has a corresponding retrospective entry
- [ ] No items in sprint-status.yaml that don't exist in the epics document set

### Parsing Verification

Compare the epics document set against generated sprint-status.yaml:

```
Epic Files Contains:                Sprint Status Contains:
✓ Epic 1                            ✓ epic-1: [status]
  ✓ Story 1.1: User Auth              ✓ 1-1-user-auth: [status]
  ✓ Story 1.2: Account Mgmt           ✓ 1-2-account-mgmt: [status]
  ✓ Story 1.3: Plant Naming           ✓ 1-3-plant-naming: [status]
                                      ✓ epic-1-retrospective: [status]
✓ Epic 2                            ✓ epic-2: [status]
  ✓ Story 2.1: Personality Model      ✓ 2-1-personality-model: [status]
  ✓ Story 2.2: Chat Interface         ✓ 2-2-chat-interface: [status]
                                      ✓ epic-2-retrospective: [status]
```

### Final Check

- [ ] Total count of epics matches
- [ ] Total count of stories matches
- [ ] All items are in the expected order (epic, stories, retrospective)
- [ ] `# project:` and `project:` use the target repo identity, not config `project_name`

## Prerequisite Reporting Check

- [ ] Missing-epics blocker is based on actual files in `current_epics_dir`, not only phase-state metadata
- [ ] Existing Product Brief, PRD, and Architecture files on disk are acknowledged as present if found
- [ ] Blocked-state guidance recommends epic creation as the next step instead of incorrectly restarting earlier completed workflows
- [ ] Prerequisite discovery is limited to the narrow paths needed for sprint planning, not broad scans across all of `planning/`
