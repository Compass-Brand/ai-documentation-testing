---
description: Close a completed beads issue
argument-hint: [issue-id] [reason]
---

Use the shell tool to close an issue:

```bash
bd close <id> --reason "..."
```

After closing, suggest checking for newly unblocked work with `bd-ready`.
