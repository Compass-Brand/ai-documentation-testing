---
name: update-standards
description: Add project-specific documentation overrides without modifying baseline policies
menu-code: US
---

# Update Standards

Update `docs/human/policies/user-overrides.md` with user-specific documentation preferences.

## Rules

- Never overwrite baseline framework policy files copied from the built-in framework.
- Only modify `docs/human/policies/user-overrides.md`.
- Record additions with date and rationale.
- If the file does not exist, create it with a header explaining its purpose.

## Process

1. Ask the user what documentation standard or preference they want to add or change.
2. Read `docs/human/policies/user-overrides.md` if it exists.
3. Add the new override entry with today's date and the user's rationale.
4. Confirm the change with the user before saving.
