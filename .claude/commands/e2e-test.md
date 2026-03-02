---
description: Run comprehensive E2E testing using agent-browser — researches codebase, tests every user journey, takes screenshots, validates database records, and fixes bugs found
---

# E2E Test

## Usage

/e2e-test

## What This Command Does

1. Checks platform compatibility (Linux/WSL/macOS only) and installs agent-browser if needed
2. Launches 3 parallel research sub-agents (app structure, database schema, bug hunting)
3. Starts the application dev server
4. Creates a task for each user journey discovered
5. Tests every journey with agent-browser: screenshots, UI validation, database checks
6. Fixes issues found during testing
7. Runs responsive testing across mobile, tablet, and desktop viewports
8. Produces a summary report with option to export detailed markdown

## Invoked Components

- Skill: e2e-test

## Example

```bash
/e2e-test
```
