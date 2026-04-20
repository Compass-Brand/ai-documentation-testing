# GitHub Baseline Bundle

Last reviewed: 2026-02-24

This directory is the source for distributed `.github/` defaults.

## Included

- `workflows/`
- `dependabot.yml`
- `CODEOWNERS`
- `profiles/` (repo-type overlays such as Node/Python/submodule dependabot variants)

## Installer Selection

The push/install surface can install either the full GitHub bundle or a selected subset.

Common examples:

```bash
# full GitHub bundle
compass-engine push --targets github

# baseline plus linting only
compass-engine push --targets github --github-features baseline,linting

# baseline plus a repo overlay
compass-engine push --targets github --github-features baseline,profile-node
```

Available GitHub feature groups:

- `baseline`
- `codeowners`
- `dependabot`
- `quality-checks`
- `linting`
- `codeql`
- `pr-size-labeler`
- `stale`
- `necessist`
- `runtime-security`
- `submodule-security-monitoring`
- `profile-node`
- `profile-python`
- `profile-submodule-compass-engine`
- `profile-submodule-bmad-method`
- `profile-check-bmad-updates`

## CodeQL Enablement in Target Repositories

The baseline includes `.github/workflows/codeql.yml`, but CodeQL will only run after repository-level security settings are enabled.

1. Apply this baseline to the target repository.
2. In target repo settings, enable:
   - `Code scanning` (`Settings` -> `Security` -> `Code security and analysis`)
3. For private/internal repositories, enable GitHub Advanced Security.

## Verification

After enabling settings, open a PR and confirm:

- `CodeQL Security Scanning / Analyze` passes.

Optional API check:

```bash
gh api repos/<owner>/<repo>/code-scanning/alerts?per_page=1 --include
```

Expected:

- HTTP `200` from the Code Scanning API.
