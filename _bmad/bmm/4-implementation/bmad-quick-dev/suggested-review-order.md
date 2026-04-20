# Shared Template: Suggested Review Order

**Purpose:** Shared generation rules for the `## Suggested Review Order` section of a spec-trace file. Reused by both `steps/step-07-spec-trace.md` (standard-pipeline trace) and `steps/step-oneshot.md` (short-circuit one-shot trace).

Ported from upstream BMAD `BMAD-METHOD/src/bmm-skills/4-implementation/bmad-quick-dev/step-05-present.md` § "Generate Suggested Review Order". The JS helper `generateSpecTrace(...)` in `tools/quick-dev-scan.js` implements these rules — call it from the step files so the output stays deterministic. The rules below describe the contract that helper honors.

---

## RULES

Build the trail as an ordered sequence of **stops** — clickable `path:line` references with brief framing — optimized for a human reviewer reading top-down to understand the change:

1. **Order by concern, not by file.** Group stops by the conceptual concern they address (e.g., "validation logic", "schema change", "UI binding"). A single file may appear under multiple concerns.
2. **Lead with the entry point** — the single highest-leverage file:line a reviewer should look at first to grasp the design intent.
3. **Inside each concern**, order stops from most important / architecturally interesting to supporting. Lightly bias toward higher-risk or boundary-crossing stops.
4. **End with peripherals** — tests, config, types, docs, and other supporting changes come last. The helper detects peripheral concerns by concern-name regex (`test`, `tests`, `config`, `type(s)`, `style`, `lint`, `doc(s)`, `fixture(s)`); route any peripheral stops into a concern with one of those names so ordering is correct.
5. **Every code reference is a clickable spec-file-relative link.** Compute each link target as a relative path from `{spec_file}`'s directory to the changed file. Format each stop as a markdown link: `` [`short-name:line`](../../path/to/file.ts#L42) ``. Use a `#L` line anchor. Use the file's basename (or shortest unambiguous suffix) plus line number as the link text. The relative path must be dynamically derived — never hardcode the depth.
6. **Each stop gets one ultra-concise line of framing** (≤15 words) — why this approach was chosen here and what it achieves in the context of the change. No paragraphs.

Format each stop as framing first, link on the next indented line:

```markdown
## Suggested Review Order

**{Concern name}**

- {one-line framing}
  [`file.ts:42`](../../src/path/to/file.ts#L42)

- {one-line framing}
  [`other.ts:17`](../../src/path/to/other.ts#L17)

**{Next concern}**

- {one-line framing}
  [`file.ts:88`](../../src/path/to/file.ts#L88)
```

> The `../../` prefix above is illustrative — the helper computes the actual relative path from `{spec_file}`'s directory to each target file using `node:path.relative`.

When there is only one concern, omit the bold label — just list the stops directly.

---

## HOW TO INVOKE

From `steps/step-07-spec-trace.md` or `steps/step-oneshot.md`, after the diff + concern-grouping are prepared:

```js
import { generateSpecTrace } from './tools/quick-dev-scan.js';

const body = generateSpecTrace({
  intent: '<original user intent>',
  route: 'standard' | 'one-shot',
  changes: [
    { path, line, concern, framing },
    // ...
  ],
  slug: '<derived from intent>',
  title: '<human-readable title>',
  problem: '<one-sentence problem statement>',
  approach: '<one-sentence approach>',
  specFileDir: '<relative dir the spec lives in>',
});
```

The helper returns the full markdown document (frontmatter + `# Title` + `## Intent` + `## Suggested Review Order`). Write it to `{implementation_artifacts}/spec-{slug}.md`. Both routes MUST set `status: 'done'` in the frontmatter — the helper enforces this.

---

## CONTRACT

Output frontmatter MUST contain:

- `title: '<title>'`
- `route: 'standard'` (step-07 path) **or** `route: 'one-shot'` (step-oneshot path)
- `status: 'done'`

Output body MUST contain, in order:

1. `# <title>`
2. `## Intent` with `**Problem:** ...` and `**Approach:** ...` lines
3. `## Suggested Review Order` built per the RULES above

If the changes array is empty, the helper emits a `_No file changes captured._` placeholder under the Suggested Review Order heading — that is a valid outcome when no tracked files changed (e.g., doc-only commits), not an error.
