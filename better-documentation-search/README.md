# Better Documentation Search: AGENTS.md Docs Index Pattern

## Source

Based on Vercel's research: [AGENTS.md outperforms skills in our agent evals](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) (January 27, 2026) by Jude Gao.

## The Core Insight

A compressed documentation index embedded directly in `AGENTS.md` (or `CLAUDE.md`) dramatically outperforms skill-based retrieval for teaching AI coding agents framework-specific knowledge. In Vercel's eval suite targeting Next.js 16 APIs absent from model training data, the docs-index approach achieved a **100% pass rate** compared to 79% for skills with explicit instructions and 53% for both skills with default behavior and baseline (no docs).

## The Problem

AI coding agents rely on training data that goes stale. When frameworks introduce new APIs (like Next.js 16's `'use cache'`, `connection()`, `forbidden()`), agents generate incorrect code or fall back to older patterns. The reverse also applies — agents running against older framework versions may suggest APIs that don't exist yet in the project.

## Two Approaches Tested

### Skills (On-Demand Retrieval)

[Skills](https://agentskills.io/) are an open standard for packaging domain knowledge into bundles of prompts, tools, and documentation that agents invoke on demand. The agent must recognize when it needs framework help, invoke the skill, and then use the docs.

**Results:**

| Configuration                  | Pass Rate | vs. Baseline |
| ------------------------------ | --------- | ------------ |
| Baseline (no docs)             | 53%       | —            |
| Skill (default behavior)       | 53%       | +0pp         |
| Skill with explicit instructions | 79%     | +26pp        |

Key finding: In **56% of eval cases**, the skill was never invoked. The agent had access to the docs but chose not to use them. Even with explicit `AGENTS.md` instructions telling the agent to use the skill, wording was fragile — subtle phrasing differences caused large behavioral swings.

### AGENTS.md Docs Index (Passive Context)

`AGENTS.md` is a markdown file in the project root that provides persistent context to coding agents on every turn, without the agent needing to decide to load it. Instead of embedding full documentation, the approach embeds a **compressed index** (~8KB, down from ~40KB) that maps directory paths to doc files. The agent reads specific files as needed.

**Results:**

| Configuration                  | Pass Rate | vs. Baseline |
| ------------------------------ | --------- | ------------ |
| Baseline (no docs)             | 53%       | —            |
| Skill (default behavior)       | 53%       | +0pp         |
| Skill with explicit instructions | 79%     | +26pp        |
| **AGENTS.md docs index**       | **100%**  | **+47pp**    |

Detailed breakdown — Build / Lint / Test all at 100%.

## Why Passive Context Wins

1. **No decision point.** The information is always present — the agent never has to decide "should I look this up?"
2. **Consistent availability.** Skills load asynchronously and only when invoked. `AGENTS.md` content is in the system prompt for every turn.
3. **No ordering issues.** Skills create sequencing decisions (read docs first vs. explore project first). Passive context avoids this entirely.

## The Key Instruction

A single directive embedded in the index drives retrieval-led behavior:

```
IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for any [framework] tasks.
```

This shifts the agent from relying on potentially outdated training data to consulting the provided docs.

## Compressed Format Specification

The index uses a pipe-delimited, brace-grouped structure:

```
<!-- MARKER-START -->[Docs Index Name]|root: ./path-to-docs
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for any [framework] tasks.
|section/path:{file1.mdx,file2.mdx,file3.mdx}
|section/path/subsection:{file4.mdx,file5.mdx}
<!-- MARKER-END -->
```

This compresses a full documentation tree into ~8KB while maintaining 100% eval performance — an 80% reduction from the uncompressed ~40KB form.

## Practical Recommendations

- **Don't wait for skills to improve.** The gap may close as models get better at tool use, but results matter now.
- **Compress aggressively.** An index pointing to retrievable files works just as well as full docs in context.
- **Test with evals.** Build evals targeting APIs not in training data — that's where doc access matters most.
- **Design for retrieval.** Structure docs so agents can find and read specific files rather than needing everything upfront.
- **Skills still have a place.** They work better for vertical, action-specific workflows (upgrades, migrations, applying best practices). The two approaches complement each other.

## Project Structure

```
better-documentation-search/
├── README.md                         # This file
├── example/
│   └── example.md                    # Extracted Next.js AGENTS.md docs index
└── scripts/
    ├── generate_docs_index.py        # Python tool to generate docs indexes
    ├── sources.example.yaml          # Example sources configuration
    └── output.example.md             # Example output
```

## Generating Your Own Docs Index

See `scripts/generate_docs_index.py` for a self-contained Python tool that crawls documentation sources and generates compressed docs index files in the AGENTS.md format. Requires Python 3.14+.
