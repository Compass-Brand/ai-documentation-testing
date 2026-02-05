# Engineering the optimal AGENTS.md for AI coding agents

AI coding agents achieve **100% task completion** with compressed documentation indexes versus 79% with on-demand skills, according to Vercel's January 2026 evaluations. This finding has catalyzed a new engineering discipline: structuring project knowledge for agent consumption. The gap isn't theoretical—it's 21 percentage points of real-world task success. Here's what the research reveals about improving compressed indexes, the tooling landscape, and hybrid approaches that combine passive context with intelligent retrieval.

## Why compressed indexes outperform skills by 21 points

Vercel's evaluation tested Next.js 16 APIs absent from model training data—`connection()`, `'use cache'`, `cacheLife()`, and async `cookies()`—where documentation access determines success. The compressed AGENTS.md approach achieved perfect scores while skills-based retrieval plateaued at 79%, even with explicit "you MUST invoke the skill" instructions.

The failure mode is illuminating: **in 56% of test cases, agents never invoked available skills**. The agent could access documentation but chose not to. Three factors explain this:

- **No decision point**: AGENTS.md content is present on every turn; agents never face "should I look this up?"
- **Ordering effects**: Instructions like "read docs first" caused agents to anchor on documentation patterns while missing project-specific context
- **Consistent availability**: Skills load asynchronously and only when invoked; passive context is always present

Vercel's compressed format reduced **40KB of documentation to 8KB** (80% reduction) using pipe-delimited, brace-grouped structure: `01-app/01-getting-started:{01-installation.mdx,02-project-structure.mdx}`. The index maps directory paths to filenames, with agents reading specific files on demand from a `.next-docs/` directory.

## Smarter compression beyond pipe-delimited format

The pipe-delimited format works, but research suggests meaningful improvements in token efficiency and agent comprehension.

**Format performance varies dramatically by encoding.** An October 2025 study testing GPT-5 Nano, Llama 3.2 3B, and Gemini 2.5 Flash Lite found YAML outperformed XML by 17.7 percentage points, with one format producing 54% more correct answers than another. For identical data, Markdown consumes **34% fewer tokens than JSON**, while XML requires **80% more tokens**. The emerging TOON (Token-Oriented Object Notation) format achieves 30-60% savings by eliminating brackets, quotes, and commas through Python-like indentation.

| Format | Tokens vs JSON | LLM Accuracy | Recommendation |
|--------|---------------|--------------|----------------|
| Markdown | 34% fewer | Very Good | Documentation indexes |
| YAML | 27% fewer | Best overall | Nested configuration |
| TOON | 30-60% fewer | Good | Tabular data |
| JSON | Baseline | Poor-Moderate | Classification only |
| XML | 19% more | Worst | Never for LLM contexts |

**Semantic compression can reduce prompts by ~80%** while preserving meaning, according to research published in arXiv 2024. This enables leveraging roughly 5× more tokens than raw context limits allow. The technique works through topic modeling that segments and compresses chunks independently, generalizing to texts 6-8× longer without fine-tuning.

**Practical format improvements include:**

- **YAML frontmatter with metadata**: Priority scores (`priority: high`), last-updated timestamps, and related file pointers enable agents to make informed fetch decisions
- **Inline micro-summaries**: `## Testing [Run pytest, CI required before merge]` lets agents decide whether to read full sections
- **Dependency graphs**: `related: [auth.md, database.md]` documents which docs depend on others for progressive fetching
- **Three-tier boundaries**: Explicitly mark actions as ✅ Always do / ⚠️ Ask first / ❌ Never do

A critical finding from "Let Me Speak Freely?" research: format restrictions **significantly decline LLMs' reasoning abilities**. Stricter constraints cause greater performance degradation—JSON mode caused GPT-3.5-Turbo to place "answer" before "reason" in 100% of responses, short-circuiting chain-of-thought reasoning. The recommendation: use the loosest format that still provides structure.

## Context budget reality: 8KB is negligible

Modern context windows make the 8KB index essentially free. Claude Sonnet 4's 200K window means **8KB consumes just 1%** of available budget; with the 1M beta, it drops to 0.2%. Gemini 2.5 Pro's 2M token window reduces it to 0.1%. The real constraint isn't raw size but **information density and position**.

The "lost in the middle" phenomenon, documented by Liu et al. 2024, shows LLMs exhibit U-shaped performance: highest accuracy when relevant information appears at the **beginning or end** of context, with performance degrading by more than 30% when critical information sits in the middle. Mitigation strategies include:

- Position highest-priority instructions at document start and end
- Place supporting details in the middle sections
- Use attention-based document reordering for retrieved content
- Implement Multi-scale Positional Encoding (Ms-PoE) for plug-and-play improvement

**Quantitative guidance from research:**

- Keep AGENTS.md under **300 lines** (ideally 60 lines for root file)
- Target **150-200 total instructions** maximum—frontier models follow this many with reasonable consistency
- Aim for **60-70% context window utilization** for RAG chunks (not 100%)
- Use **512-1024 token chunks** for retrievable sections

## The tooling landscape for generating and maintaining indexes

Three official tools exist for AGENTS.md generation, with a growing ecosystem of community alternatives.

**Official tools:**

`npx @next/codemod@canary agents-md` detects your Next.js version, downloads matching documentation via git sparse-checkout to `.next-docs/`, and injects the compressed index between `<!-- NEXT-AGENTS-MD-START -->` markers. This is production-ready with Vercel's 100% eval pass rate validation.

Claude Code's `/init` command analyzes your project and generates a starter CLAUDE.md by scanning codebase structure. This ships with every Claude Code subscription.

Nx's MCP server (`npx nx-mcp@latest`) auto-configures monorepo workspaces for AI agents, creating/updating AGENTS.md and CLAUDE.md with deep workspace context.

**Community generators:**

AgentRules Architect (99 GitHub stars) runs a 6-phase analysis pipeline—discovery → planning → deep dives → synthesis → consolidation → generation—supporting Anthropic Claude, OpenAI GPT-5.x, Google Gemini, DeepSeek, and xAI Grok. It outputs AGENTS.md, .cursorignore, and per-phase snapshots.

For Cursor rules specifically, awesome-cursorrules provides a curated collection of .cursorrules files across tech stacks (React, Next.js, Angular, Vue, TypeScript), with a companion VSCode extension.

**The major gap**: No plugins exist for auto-generating AI documentation indexes from Docusaurus, MkDocs, Sphinx, VitePress, or Nextra. This represents a significant tooling opportunity—these frameworks already contain structured documentation that could be transformed into AGENTS.md format.

**Maintenance approaches:**

The Claude Code GitHub Action (`anthropics/claude-code-action`) provides CI patterns for documentation sync, including automatic PR review triggers and scheduled maintenance workflows. For local development, the source-agents tool keeps AGENTS.md and CLAUDE.md synchronized across projects, scanning for inconsistencies and fixing symlinks.

Git hooks remain the pragmatic approach for most teams: pre-commit validation that the index matches actual documentation structure, with CI enforcement on pull requests.

## Hybrid approaches layer passive context with smart retrieval

The highest-performance architecture combines persistent indexes with progressive disclosure—agents get a high-level map passively but drill into details on demand.

**The Claude-Mem pattern quantifies the efficiency gain:**

Traditional RAG injects 25,000 tokens of past context at session start; the agent finds 1 relevant observation buried in the middle. Total tokens consumed: 25,000. Relevant tokens: ~200. **Efficiency: 0.8%**.

Progressive disclosure shows an 800-token index at session start; the agent sees titles, decides relevance, fetches a specific 155-token observation. Total consumed: 955. Relevant tokens: 955. **Efficiency: 100%**.

This represents a **26× improvement** in context efficiency through layered information architecture.

**Three-tier context strategy:**

| Tier | What goes here | Token budget | Loading mechanism |
|------|---------------|--------------|-------------------|
| System prompt | Critical universally-applicable rules | 2-5K tokens | Always present |
| Passive index | Lightweight table of contents with IDs, titles, types, token costs | 5-10K tokens | Loaded on session start |
| On-demand retrieval | Full documentation content, code examples, detailed specs | Unbounded | Tool calls (grep, glob, MCP) |

**MCP as the retrieval layer:**

Model Context Protocol servers provide the infrastructure for index-pointed retrieval. The passive AGENTS.md contains pointers; MCP tools fetch full content when needed. The **meta-tool pattern** registers only two MCP tools instead of dozens:

1. **Discovery tool**: Description contains complete capability index
2. **Execution tool**: Handles any requested capability with unified context

This achieves **85-95% token overhead reduction** compared to registering all tools individually.

**Progressive disclosure file structure:**

```
AGENTS.md                    # Root index (~60 lines max)
├── Lightweight TOC with pointers
├── Critical universal rules
└── File references: @docs/setup.md, @docs/testing.md

agent_docs/                  # Fetched on demand
├── setup.md
├── testing.md
├── deployment.md
└── architecture.md
```

The root AGENTS.md follows BLUF (Bottom Line Up Front): commands first, project structure second, conventions third. Each section header includes a micro-summary in brackets. Agents read the root file on every turn; they fetch `agent_docs/` files only when tasks require them.

## How other agent frameworks approach the same problem

Every major AI coding assistant has converged on persistent project configuration, though formats differ.

**Cursor** uses `.cursor/rules/*.mdc` files with YAML frontmatter specifying glob patterns for auto-attachment. Rules activate automatically based on file paths being edited. Size recommendation: under 500 lines per file. Cursor explicitly supports AGENTS.md alongside its native system.

**Aider** takes a radically different approach: **automatic repository map generation** requiring no manual configuration. Tree-sitter parses the AST, extracts key symbols, builds a dependency graph, and applies PageRank to identify the most important code. Default budget: 1,024 tokens. This progressive disclosure is built into the architecture—LLMs request additional files as needed.

**Cline** implements a **Memory Bank system** for persistent project knowledge alongside `.clinerules/` folders. Auto Compact triggers at ~80% context usage, summarizing conversation to maintain continuity. AGENTS.md is explicitly supported as a fallback.

**Continue.dev** uses YAML configuration with pluggable context providers including a `@repo-map` provider inspired by Aider's approach. Rules can come from files, URLs, or inline text.

**GitHub Copilot** relies on `.github/copilot-instructions.md` plus prompt files in `.github/prompts/*.prompt.md`. Workspace indexing handles up to 2,500 files locally.

**Amazon Q Developer** uses `.amazonq/rules/` directories with Markdown files, providing explicit context transparency showing which rules were applied to responses.

The fragmentation is real—teams using multiple tools maintain parallel configurations. AGENTS.md, stewarded by the Agentic AI Foundation under the Linux Foundation, aims to standardize this. Over 60,000 open-source projects now include AGENTS.md files, and the format is supported by OpenAI Codex, Google Jules, Cursor, Factory, Aider, Devin, Windsurf, and GitHub Copilot.

## What the community has learned in production

Analysis of 2,500+ repositories and extensive Hacker News discussion (837+ points, 380+ comments) reveals practical consensus.

**What works:**

- Commands come first, wrapped in backticks with flags: `npm test --coverage`
- One real code snippet beats three paragraphs of description
- Define boundaries explicitly: what agents should always do, ask first about, or never attempt
- Nested AGENTS.md files in subdirectories for package-specific guidance
- "STOP. What you remember about [framework] is WRONG for this project. Always search docs first."

**Pain points:**

- Agents forget AGENTS.md instructions as context grows—users want forced re-reading mechanisms
- Root directory pollution from yet another config file (suggestions: `.agents/`, `.config/`, `.well-known/`)
- Maintenance burden keeping indexes synchronized with actual documentation
- No universal standard forces teams to maintain CLAUDE.md + AGENTS.md + .cursorrules + others

**Emerging best practice:** Treat AGENTS.md as an entry point, not a knowledge dump. Move detailed documentation to organized folders; the root file contains pointers and summaries. Every session where you catch and fix an agent error is an opportunity to improve the knowledge base—document what Claude gets wrong, not comprehensive manuals.

Phoenix Framework (Elixir) now ships AGENTS.md by default in new projects. The pattern: framework authors bundle agent-friendly documentation, ensuring developers using coding agents have an optimal experience from project initialization.

## Practical recommendations for engineering teams

**For immediate implementation:**

1. Adopt Markdown with YAML frontmatter as primary format—34% more token-efficient than JSON, best LLM comprehension
2. Generate compressed indexes using `npx @next/codemod agents-md` for Next.js projects or AgentRules Architect for others
3. Position critical instructions at document start and end; supporting details in middle
4. Keep root AGENTS.md under 300 lines; use `agent_docs/` folder for detailed content

**For tooling investment:**

1. Implement CI validation that documentation structure matches index
2. Build auto-generation from existing doc frameworks (Docusaurus, MkDocs)—this gap represents significant opportunity
3. Add MCP servers as retrieval layer that passive indexes point to
4. Track which documentation sections agents access to prioritize frequently-used content

**For advanced optimization:**

1. Implement two-tier index system: lightweight metadata (titles, token costs, types) plus detail-level retrieval by ID
2. Add inline micro-summaries enabling agents to decide what to read without reading everything
3. Use semantic compression for older/less-frequently-accessed documentation
4. Experiment with TOON format for tabular data (30-60% token savings)

The 21-percentage-point improvement from Vercel's research represents just the baseline. Combining compressed indexes with progressive disclosure, position-aware ordering, and MCP retrieval creates compounding gains. The teams that master context engineering will see their AI coding agents outperform those still treating documentation as an afterthought.

---

## Sources

- [AGENTS.md outperforms skills in our agent evals — Vercel Blog (Jan 2026)](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals)
- [Which Nested Data Format Do LLMs Understand Best? — Improving Agents (Oct 2025)](https://www.improvingagents.com/blog/best-nested-data-format/)
- [Let Me Speak Freely? Format Restrictions on LLM Performance — arXiv (Aug 2024)](https://arxiv.org/html/2408.02442v1)
- [Extending Context Window via Semantic Compression — ACL Findings (2024)](https://aclanthology.org/2024.findings-acl.306/)
- [Lost in the Middle: How Language Models Use Long Contexts — Liu et al. (2024)](https://arxiv.org/abs/2307.03172)
- [Context Window Utilization for RAG — arXiv (Jul 2024)](https://arxiv.org/html/2407.19794v1)
- [TOON: Token-Efficient Data Format for LLM Applications](https://abdulkadersafi.com/blog/toon-the-token-efficient-data-format-for-llm-applications-complete-guide-2025)
- [How to write a great agents.md: Lessons from 2,500+ repos — GitHub Blog](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- [Progressive Disclosure — Claude-Mem Documentation](https://docs.claude-mem.ai/progressive-disclosure)
- [The Meta-Tool Pattern: Progressive Disclosure for MCP — Synaptic Labs](https://blog.synapticlabs.ai/bounded-context-packs-meta-tool-pattern)
- [Writing a good CLAUDE.md — HumanLayer Blog](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Repository Map — Aider Documentation](https://aider.chat/docs/repomap.html)
- [AGENTS.md Specification](https://agents.md/)
- [AgentRules Architect — GitHub](https://github.com/trevor-nichols/agentrules-architect)
- [awesome-cursorrules — GitHub](https://github.com/PatrickJS/awesome-cursorrules)
- [source-agents: Keep AGENTS.md and CLAUDE.md in sync — GitHub](https://github.com/iannuttall/source-agents)
