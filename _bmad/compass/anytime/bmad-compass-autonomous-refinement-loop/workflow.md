# Workflow: Autonomous Refinement Loop

## Purpose
Autonomously harden the current working content through iterative party-mode critique and advanced elicitation remediation until zero unresolved issues remain.

## Automation Boundary
- This workflow is an intentional automation layer for BMAD.
- Manual `party-mode` and manual `advanced-elicitation` remain available as separate user-invoked workflows.
- This workflow does not invoke the interactive menu contracts of manual workflows.
- This workflow does not invoke adversarial review tasks.

## Integration Contract
When invoked from another workflow:
1. Receive current working content from the caller.
2. Run iterative autonomous party + elicitation cycles without per-iteration user confirmation prompts.
3. Maintain a persistent issue ledger across iterations.
4. Return updated content to caller only when unresolved issue count reaches zero after full re-scan.
5. If blocked on an unresolved issue, halt and escalate with blocker details.

## Mandatory Execution Rules
- Execute all steps in order.
- Use real subagents or agent-team tooling when available. Do not simulate party participants as a fallback.
- Build a party-style review process using multiple relevant agents each iteration.
- Never invoke adversarial review tasks in this workflow.
- Never present manual advanced-elicitation menus (`1-5/r/a/x`, `y/n/other`) inside this workflow.
- Auto-select advanced elicitation methods each iteration (no user method menu prompts).
- Track issues from both party findings and elicitation deltas in a persistent ledger.
- Auto-fix all open issues each iteration where a safe fix is available.
- Re-scan and re-validate ledger state after each remediation pass.
- Stop only when unresolved issue count is exactly `0` after re-scan.
- Do not apply an iteration cap or watchdog timeout.
- Do not create a separate report artifact. Update and return the target content only.
- If any open issue cannot be safely resolved in the current pass, pause and escalate immediately.

## Inputs
- `content`: the active section/draft to refine.
- `context` (optional): workflow context that clarifies intent, scope, and constraints.

## Issue Ledger Model
Maintain a persistent ledger record for each issue with:
- `id` (`I001`, `I002`, ...)
- `source` (`party|elicitation`)
- `severity` (`Critical|High|Medium|Low`)
- `status` (`open|fixed|blocked|dismissed`)
- `issue`
- `proposed_fix`
- `rationale`
- `first_seen_iteration`
- `last_updated_iteration`

### Ledger Rules
- Dedupe semantically equivalent issues into one ledger item.
- Never silently delete ledger items.
- Reopen a `fixed` issue if it reappears in any later re-scan.
- Use `dismissed` only for invalid, duplicate, or clearly out-of-scope issues; include rationale.

## Flow
### 1. Initialize Context
- Load config from `{project-root}/_bmad/core/config.yaml`.
- Load `{project-root}/_bmad/_config/agent-manifest.csv` and identify agents relevant to the artifact domain.
- Load `the bmad-compass-advanced-elicitation skill methods (methods.csv)` for remediation method selection.
- Validate `content` is present and readable. If missing, halt and request content.
- Initialize:
- `iteration = 1`
- `working_content = content`
- `issue_ledger = []`

### 2. Start Autonomous Iterative Loop
Repeat forever:

#### 2a. Build Team for This Iteration
- Create an agent team (or coordinated subagents) with:
- one facilitator/orchestrator.
- at least two domain-relevant reviewers.
- at least one implementation-focused fixer.
- Preserve diversity of viewpoint across iterations by rotating reviewers when possible.

#### 2b. Run Party Critique Round
- Use party-mode style collaboration against `working_content`.
- Produce party issue candidates with `source=party`, severity, issue text, and proposed fix.

#### 2c. Run Autonomous Advanced Elicitation Round
- Select a diverse set of 3-5 methods from `the bmad-compass-advanced-elicitation skill methods (methods.csv)`.
- Prefer category diversity and avoid repeating the same method set in consecutive iterations.
- Execute methods autonomously on `working_content` without user prompts.
- Record any newly surfaced unresolved weaknesses as issue candidates with `source=elicitation`.

#### 2d. Merge Candidates into Persistent Ledger
- Add new issues with fresh IDs and `status=open`.
- Update existing matching issues (`last_updated_iteration`, severity/proposed_fix if improved).
- Reopen any previously `fixed` issue that reappears.
- Keep `blocked` and `dismissed` records for auditability.

#### 2e. Auto-Remediate All Open Issues
- Process open issues in severity order (`Critical` to `Low`).
- For each issue:
- apply a direct fix in `working_content`.
- if multiple safe fix strategies exist, run targeted elicitation method(s) to choose and refine the strongest fix.
- after applying, tentatively mark as `fixed` with a one-line rationale.

#### 2f. Blocker Gate
- If any open issue cannot be safely fixed in this pass:
- mark the issue `blocked`.
- halt the autonomous loop immediately.
- escalate to user with:
- blocked issue `id` and `severity`.
- why safe auto-fix was not possible.
- attempted remediations.
- exact decision or missing input needed.
- Return current `working_content` plus blocker summary, then stop.

#### 2g. Full Re-Scan and Validate Ledger
- Re-run party critique and autonomous elicitation against updated `working_content`.
- Reconcile results into `issue_ledger` using ledger rules.
- Compute:
- `open_issue_count`
- `fixed_count`
- `reopened_count`
- `dismissed_count`
- `blocked_count`

#### 2h. Stop Condition and Iteration Summary
- Report concise iteration summary:
- iteration number
- methods used
- opened/fixed/reopened/dismissed/blocked counts
- current `open_issue_count`
- If `open_issue_count == 0`, return `working_content` to caller and exit.

#### 2i. Prepare Next Iteration
- Increment `iteration`.
- Repeat from step `2a`.

## Success Metrics
- Every iteration produces a traceable summary with counts and method set.
- No manual interaction prompts occur inside ORL.
- Ledger state remains internally consistent across iterations.
- Workflow exits only at zero unresolved issues or explicit blocked escalation.

## Failure Modes
- Presenting interactive advanced-elicitation menu prompts.
- Losing ledger history between iterations.
- Declaring completion before a full re-scan validates zero open issues.
- Silent failure to escalate blocked issues.

## Output
- Return the latest refined `working_content` to the caller.
- Keep output focused on the target artifact/section; do not generate separate reports.
- Include a final inline summary with total iterations and ledger disposition counts.
