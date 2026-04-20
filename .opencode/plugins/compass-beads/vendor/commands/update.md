---
description: Update a beads issue
argument-hint: [issue-id] [status]
---

Use the shell tool to update a beads issue.

Common shapes:

```bash
bd update <id> --status in_progress
bd update <id> --status blocked
bd update <id> --priority 1
```

Confirm the intended change before applying it if the user was ambiguous.
