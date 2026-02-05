# Agent Knowledge Organizer — Design Document

Date: 2026-02-05
Revised: 2026-02-05 (post-review)

## Purpose

Two Python packages help AI coding agents find and use project knowledge efficiently:

1. **agent-index** — Scans documentation sources, transforms docs into AI-optimized `.llms.md` files, and generates tiered index files (AGENTS.md / CLAUDE.md).
2. **agent-evals** — Tests index formats, structures, and doc transformations to find which produces the best agent outcomes per token.

The organizer handles structured knowledge: framework APIs, project docs, skills, workflows, runbooks.

---

## Project Structure

Both packages share a `uv` workspace, letting `agent-evals` import types from `agent-index` without duplication.

**Workspace root `pyproject.toml`:**
```toml
[project]
name = "ai-enhancements"
version = "0.1.0"

[tool.uv.workspace]
members = ["agent-index", "agent-evals"]
```

**`agent-evals/pyproject.toml` dependency** (UV requires two-part syntax):
```toml
[project]
name = "agent-evals"
dependencies = ["agent-index"]

[tool.uv.sources]
agent-index = { workspace = true }
```

**Directory structure:**
```
ai-enhancements/
├── pyproject.toml                  # uv workspace root (see above)
├── RESEARCH.md                     # Migrated from better-documentation-search/
├── planning/DESIGN.md              # Design document (in planning/)
├── agent-index/                    # The organizer package
│   ├── pyproject.toml
│   ├── src/
│   │   └── agent_index/
│   │       ├── __init__.py
│   │       ├── cli.py              # CLI entry point
│   │       ├── config.py           # Config loading (YAML/TOML)
│   │       ├── scanner.py          # Source scanning (local + GitHub)
│   │       ├── models.py           # Pydantic models (DocFile, DocTree, IndexConfig, etc.)
│   │       ├── tiers.py            # Tier system & index generation
│   │       ├── transform.py        # Doc transformation pipeline (composable steps)
│   │       ├── output.py           # Formatters & file injection
│   │       ├── scaffold.py         # --scaffold directory/template creation
│   │       ├── validate.py         # --validate CI mode
│   │       └── wizard.py           # --init interactive config generator
│   └── tests/
│
├── agent-evals/                    # The eval framework package
│   ├── pyproject.toml              # depends on agent-index = { workspace = true }
│   ├── src/
│   │   └── agent_evals/
│   │       ├── __init__.py
│   │       ├── runner.py           # Main eval harness
│   │       ├── scoring.py          # Score computation & statistics
│   │       ├── variants/           # Format variant plugins
│   │       │   ├── __init__.py     # Auto-imports all variant modules via pkgutil
│   │       │   ├── base.py         # Abstract IndexVariant base class
│   │       │   ├── registry.py     # Registry with explicit load_all() discovery
│   │       │   ├── pipe_delimited.py
│   │       │   ├── yaml_index.py
│   │       │   ├── markdown_tiered.py
│   │       │   └── toon_index.py
│   │       ├── tasks/              # Task type definitions
│   │       │   ├── base.py         # Abstract EvalTask with Pydantic models
│   │       │   ├── retrieval.py
│   │       │   ├── fact_extraction.py
│   │       │   ├── code_generation.py
│   │       │   ├── agentic.py      # End-to-end agentic tasks
│   │       │   ├── multi_hop.py
│   │       │   ├── negative.py     # Unanswerable queries
│   │       │   ├── disambiguation.py
│   │       │   ├── conflicting.py
│   │       │   ├── robustness.py
│   │       │   ├── efficiency.py
│   │       │   ├── compositional.py
│   │       │   └── loader.py       # Load tasks from YAML
│   │       ├── metrics/            # Metric implementations
│   │       │   ├── base.py         # Abstract Metric
│   │       │   ├── faithfulness.py
│   │       │   ├── tool_calls.py
│   │       │   ├── first_attempt.py
│   │       │   ├── abstention.py
│   │       │   ├── navigation.py
│   │       │   └── consistency.py
│   │       ├── fixtures/           # Test data
│   │       │   ├── sample_docs/
│   │       │   └── doc_tree.json
│   │       └── llm/               # LLM interaction via LiteLLM
│   │           ├── client.py       # Thin wrapper around litellm.completion()
│   │           ├── cache.py        # Disk-backed response cache
│   │           └── token_counter.py
│   ├── task_data/                  # YAML test case definitions
│   └── reports/                    # Output directory
```

Delete `better-documentation-search/` after migrating RESEARCH.md to the project root.

---

## AI-Optimized File Convention: `.llms.md`

Transformed docs use the `.llms.md` extension, inspired by [llms.txt](https://llmstxt.org/). This makes AI-specific files easy to find (e.g., `glob **/*.llms.md`).

**Default: co-located files.** AI-optimized docs sit beside their human counterparts:

```
docs/
├── architecture.md               # Human-readable
├── architecture.llms.md          # AI-optimized (generated)
├── guides/
│   ├── auth.md
│   ├── auth.llms.md
```

**Alternative: separate directory.** Configure a `.agent-docs/` directory instead:

```
.agent-docs/
├── required/
│   ├── architecture.llms.md
├── recommended/
│   ├── api/auth.llms.md
```

AGENTS.md always points to `.llms.md` files regardless of location strategy.

---

## Data Models (Pydantic)

All models use Pydantic v2 for validation, serialization, and schema generation.

```python
from pydantic import BaseModel, Field
from datetime import datetime

class DocFile(BaseModel):
    """A single documentation file with metadata."""
    rel_path: str                           # "guides/auth.md"
    content: str                            # raw file content
    size_bytes: int
    token_count: int | None = None          # estimated via tiktoken or heuristic
    tier: str                               # "required" | "recommended" | "reference" | custom
    section: str                            # grouping label: "API", "Guides"
    priority: int = 0                       # for position-aware ordering
    content_hash: str = ""                  # SHA-256 for staleness detection
    last_modified: datetime | None = None
    summary: str | None = None              # micro-summary for index metadata
    related: list[str] = Field(default_factory=list)  # related file paths

class DocTree(BaseModel):
    """Collection of documentation files with tree-level metadata."""
    files: dict[str, DocFile]               # keyed by rel_path
    scanned_at: datetime
    source: str                             # local path or GitHub URL
    total_tokens: int = 0                   # cached sum across all files

class TierConfig(BaseModel):
    """Configuration for a single documentation tier."""
    name: str
    instruction: str
    patterns: list[str] = Field(default_factory=list)  # glob patterns for file assignment

class TransformStep(BaseModel):
    """A single step in the transformation pipeline."""
    type: str                               # "passthrough" | "algorithmic" | "llm"
    strategy: str = "default"               # "compressed" | "restructured" | "tagged"
    model: str | None = None                # for LLM steps

class IndexConfig(BaseModel):
    """Full configuration for generating a docs index."""
    index_name: str = "Docs Index"
    marker_id: str = "DOCS"
    root_path: str = "./.docs"
    instruction: str = "Prefer retrieval-led reasoning over pre-training-led reasoning."
    fallback_command: str = ""

    tiers: list[TierConfig] = Field(default_factory=lambda: [
        TierConfig(name="required", instruction="Read these files at the start of every session."),
        TierConfig(name="recommended", instruction="Read these files when working on related tasks."),
        TierConfig(name="reference", instruction="Consult these files when you need specific details."),
    ])

    sources: list[dict] = Field(default_factory=list)
    file_extensions: set[str] = {".md", ".mdx", ".rst", ".txt"}
    ignore_patterns: list[str] = ["node_modules", "__pycache__", ".git", ".venv"]

    # Output
    output_file: str = ""
    inject_into: str = ""
    format: str = "tiered"                  # "flat" | "tiered" | "yaml-index"
    file_strategy: str = "colocate"         # "colocate" (.llms.md next to source) | "directory" (.agent-docs/)

    # Transform pipeline (composable steps)
    transform_steps: list[TransformStep] = Field(default_factory=lambda: [
        TransformStep(type="passthrough")
    ])

    # LLM config (shared by transform and future features)
    llm_provider: str = ""                  # "anthropic" | "openai" | "local"
    llm_model: str = ""
    llm_base_url: str = ""                  # for local models

    # Cross-tool output
    output_targets: list[str] = Field(default_factory=lambda: ["agents.md"])
    # Options: "agents.md", "claude.md", "cursor-rules", "copilot-instructions"

    max_workers: int = 8
```

---

## The Organizer: Three-Stage Pipeline

### Scan → Transform → Output

**Scan** reads docs from local directories and GitHub repos. Produces a `DocTree` with metadata and content hashes for incremental processing.

**Transform** converts human docs into AI-optimized `.llms.md` versions. The pipeline is composable — steps execute sequentially, each receiving output from the previous.

```yaml
# Simple: no transformation
transform_steps:
  - type: passthrough

# Algorithmic only (no LLM needed)
transform_steps:
  - type: algorithmic
    strategy: compressed

# Hybrid: algorithmic cleanup then LLM refinement
transform_steps:
  - type: algorithmic
    strategy: compressed
  - type: llm
    strategy: restructured
```

Transform strategies:
- **Passthrough** — copies as-is (baseline, default)
- **Algorithmic compressed** — regex/heuristic cleanup, no LLM needed
- **LLM compressed** — LLM rewrites for conciseness
- **LLM restructured** — LLM reorders for lookup (signatures first, parameters in tables)
- **LLM tagged** — LLM compresses + adds semantic markers

**Incremental transforms:** The scanner stores `content_hash` per file in `.agent-index-state.json`. On subsequent runs, only files whose hash has changed are re-transformed. This avoids redundant LLM calls.

**Error handling for LLM transforms:**
- Per-file retry with exponential backoff (max 3 attempts)
- Per-file fallback to passthrough on permanent failure
- Partial result preservation — a 50-file transform that fails on file 37 keeps the first 36 results
- Transform state saved to `.agent-index-state.json` for resumability

**LLM provider:** Uses [LiteLLM](https://github.com/BerriAI/litellm) for unified access to 100+ providers (Anthropic, OpenAI, Ollama, vLLM, llama.cpp, LM Studio, and more). LiteLLM presents an OpenAI-compatible interface (`litellm.completion()`) but translates internally to each provider's native API.

```yaml
llm_provider: "anthropic"
llm_model: "claude-sonnet-4-20250514"

# Or local:
llm_provider: "ollama"
llm_model: "llama3"
llm_base_url: "http://localhost:11434"
```

**Output** generates the tiered AGENTS.md index pointing to `.llms.md` files.

---

## The Tiered Index System

The root AGENTS.md is a lean pointer file. Agents follow the pointers to read the actual `.llms.md` files via tool calls.

### Default Three Tiers (Flexible Depth)

Users define tiers in config. The default provides three; users can add or remove them.

```yaml
tiers:
  - name: required
    instruction: "Read these files at the start of every session before doing any work."
    patterns: ["**/README.md", "**/ARCHITECTURE.md", "**/CONVENTIONS.md"]
  - name: recommended
    instruction: "Read these files when working on related tasks."
    patterns: ["docs/guides/**"]
  - name: reference
    instruction: "Consult these files when you need specific details."
    patterns: ["docs/api/**", "docs/config/**"]
```

### Required Tier: Inline vs. Pointer (Eval-Determined)

The required tier points to files like the root README, coding standards, and architecture docs — must-know context for any session. Whether to inline these in AGENTS.md or keep them as pointers is an open question the eval framework will answer.

The eval framework tests both approaches:
- **Pointer-based required tier** — AGENTS.md lists paths, agents read them via tool calls
- **Inline required tier** — required content embedded directly in AGENTS.md as passive context

If evals show inlining required content meaningfully improves agent performance, the organizer will support an `inline_required: true` config option.

### Position-Aware Ordering (BLUF)

Content follows Bottom Line Up Front ordering for readability:
- Commands and critical instructions at top
- Required tier pointers next
- Recommended and reference tiers in the middle
- Boundary rules and repeated retrieval instruction at bottom

At ~2-3K tokens for a typical AGENTS.md, "lost in the middle" effects are minimal. BLUF serves as sound information architecture.

### Generated Output (Illustrative)

```markdown
IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.

## Required [Read at session start before doing any work]

README.llms.md
docs/architecture.llms.md
docs/conventions.llms.md

## Recommended [Read when working on related tasks]

### API
docs/api/auth.llms.md
docs/api/routes.llms.md

### Testing
docs/testing/unit-tests.llms.md
docs/testing/integration.llms.md

## Reference [Consult when you need specific details]

### Deployment
docs/deployment/docker.llms.md
docs/deployment/ci-cd.llms.md

IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.
```

The exact entry format (path only, path + summary, path + token estimate) is determined by eval results. The output formatter is pluggable.

### Cross-Tool Output

AI coding tools consume documentation differently. The organizer generates multiple output files:

- **AGENTS.md** — Standard format (supported by Codex, Jules, Cursor, Aider, Devin, Windsurf, Copilot). Compliance with the [AGENTS.md specification](https://agents.md/) is the default.
- **CLAUDE.md** — Claude Code-specific format
- **.cursor/rules/*.mdc** — Cursor rules with YAML frontmatter and glob patterns
- **.github/copilot-instructions.md** — GitHub Copilot format

```yaml
output_targets:
  - agents.md
  - claude.md
  - cursor-rules
```

---

## The Eval Framework

### Purpose

Determine which index format, structure, metadata level, and doc transformation produces the best agent outcomes per token. Testing spans multiple models to ensure findings generalize. The framework measures the full chain: retrieval accuracy, extraction, generation, and end-to-end agentic performance.

### Core Concepts

**Variant** — A specific index configuration. Discovered via `registry.load_all()`, which uses `pkgutil` to import modules from `variants/`. Add a variant by creating one file with a registered class.

Variants take no parameters — each class encapsulates its configuration. If a variant family needs multiple configurations (e.g., YAML with different metadata levels), create a separate class for each.

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class VariantMetadata(BaseModel):
    """Declares which axis and category a variant belongs to."""
    name: str                    # "yaml-with-summaries"
    axis: int                    # 1-10, which eval axis this variant tests
    category: str                # Human-readable axis name: "structure", "format", etc.
    description: str             # One-line description for reports
    token_estimate: int = 0      # Estimated index tokens (populated after render)

class IndexVariant(ABC):
    """Base class for all index format variants."""

    @abstractmethod
    def metadata(self) -> VariantMetadata:
        """Return variant identity and axis membership."""
        ...

    @abstractmethod
    def render(self, doc_tree: "DocTree") -> str:
        """Generate the full index content from a documentation tree.
        Returns the complete index as a string (e.g., markdown, YAML, etc.)."""
        ...

    def setup(self, doc_tree: "DocTree") -> None:
        """Optional: pre-processing before render (e.g., compute summaries).
        Called once per eval run, not per task."""
        pass

    def teardown(self) -> None:
        """Optional: cleanup after all tasks for this variant complete."""
        pass
```

The registry provides `get_variants_for_axis(axis: int) -> list[IndexVariant]` and `get_all_variants() -> list[IndexVariant]` for the runner.

**Task** — A question with a known answer. Implements `build_prompt()` and `score_response()`. Defined in YAML; validated by Pydantic:

```yaml
# task_data/retrieval/api_auth_lookup.yaml
type: retrieval
question: "Which file documents the OAuth2 authentication flow?"
expected_files: ["docs/api/auth.llms.md"]
domain: framework_api
difficulty: easy
tags: [single-hop, api]
```

**Task YAML schemas per type.** All tasks share base fields (`task_id`, `type`, `question`, `domain`, `difficulty`, `tags`, `metadata`). Each type adds:

| Type | Additional Fields |
|------|-------------------|
| **Retrieval** | `expected_files: list[str]`, `evidence_passage: str` |
| **Fact extraction** | `expected_answer: str`, `answer_aliases: list[str]`, `source_location: str`, `fact_type: enum` |
| **Code generation** | `expected_answer: str`, `test: str` (unittest), `entry_point: str`, `canonical_solution: str`, `libs: list[str]`, `doc_struct: dict` |
| **End-to-end agentic** | `expected_tools: list[ToolCall]`, `files: dict` (sandbox provisions), `setup_script: str`, `FAIL_TO_PASS: str` (JSON array), `PASS_TO_PASS: str` (JSON array), `message_limit: int`, `token_limit: int` |
| **Multi-hop reasoning** | `expected_answer: str`, `answer_aliases: list[str]`, `paragraphs: list[{idx, title, text, is_supporting}]`, `question_decomposition: list[{id, question, answer, paragraph_support_idx}]`, `hop_count: int` |
| **Negative/unanswerable** | `answerable: bool` (always false), `expected_behavior: enum` (abstain \| cite_absence), `nearest_miss: str` (closest-but-wrong passage) |
| **Compositional code gen** | Same as code generation plus `apis: list[dict]` (multiple API doc structs), `integration_points: str` |
| **Robustness** | `base_task_id: str` (unperturbed version), `perturbation: {type: enum, original_input: str, description: str}` — inherits remaining fields from base type |
| **Disambiguation** | `interpretations: list[{interpretation, answer, matching_entry_id}]`, `ambiguity_type: enum` (lexical \| scope \| entity \| temporal), `matching_entries: list[str]` |
| **Conflicting info** | `sources: list[{source_id, content, claim, authority_level}]`, `conflict_type: enum` (version_mismatch \| factual_contradiction \| deprecated), `resolution: {authoritative_source_id, correct_answer}`, `expected_behavior: enum` (flag_conflict \| prefer_authoritative \| present_both) |
| **Efficiency-constrained** | `base_task_id: str`, `token_budget: int`, `message_limit: int`, `time_limit: int` — inherits remaining fields from base type |

Task IDs encode type: `retrieval_001`, `multihop_042`, `robustness_retrieval_001`. Ground truth uses `expected_answer` for string-match types and `test` + `FAIL_TO_PASS` for execution-based types. At least one is required per task.

**SWE-bench field format note:** SWE-bench Verified stores `FAIL_TO_PASS` and `PASS_TO_PASS` as JSON strings in the HuggingFace dataset, not Python lists. Use `json.loads()` to parse them.

**Runner** — Sends each task to each variant across LLM providers via LiteLLM. Runs N repetitions per trial and caches responses to disk.

**Reporter** — Aggregates results into comparison tables showing statistical significance, sensitivity analysis, and per-axis summaries. Includes cost breakdowns and saturation analysis.

### Statistical Methodology

**Repetitions:** N=10 minimum per trial. (At N=5, Wilcoxon signed-rank cannot reach p<0.05; minimum p is 0.0625.) N=16 for final comparison of top candidates.

**Power analysis:** At N=16 with a large effect (Cohen's d=0.8), power is ~80-85% for Wilcoxon signed-rank. For medium effects (d=0.5), power drops to 50-60%. The composite score scale (0-100) with expected SD ~10 means a 5-point difference corresponds to d=0.5 (medium effect). To detect smaller differences reliably, use N=25+. Validate sample size via R's `MKpower::sim.ssize.wilcox.test()` before committing to full runs.

**Primary test:** Pairwise Wilcoxon signed-rank tests with Holm-Bonferroni correction for multiple comparisons. Effect sizes reported as rank-biserial correlation alongside p-values.

**Confidence intervals:** 95% bootstrap CIs (10,000 resamples, BCa method) for all point estimates. BCa (bias-corrected and accelerated) intervals correct for bias and skewness — essential for small samples (N=10-16).

**Domain modeling:** Domain (framework API, project repo, skills/workflows) modeled as a fixed effect in ANOVA-style analysis, or as a random effect in mixed-effects regression. This replaces clustered standard errors with 3 clusters (invalid: clustered SEs require 30+ clusters for consistent estimates).

**Temperature:** Primary evaluation at temperature 0.3 (matches typical agent deployment). Secondary runs at 0.0 and 0.7 to characterize robustness. Temperature 0.0 does not guarantee determinism (GPU floating-point variance); N repetitions at any temperature capture real variance.

**Sensitivity analysis:** Results reported under five weighting schemes:
- Default weights (see Task Types section)
- Retrieval-heavy: core retrieval tasks at +0.05 each, edge cases reduced
- Code-heavy: code generation tasks at +0.05 each, retrieval reduced
- Agentic-heavy: end-to-end agentic (type 4) upweighted to 0.20, others reduced proportionally
- Uniform weights: 1/11 = 0.0909 for each type (tests whether ranking is weight-dependent at all)

If the winner changes under different weights, report that fragility and prefer the most robust candidate.

### Baselines

Each axis comparison includes four baselines:

| Baseline | Description | Purpose |
|----------|-------------|---------|
| **No-index** | Agent receives no documentation index at all | Lower bound: how much does any index help? |
| **No-docs** | Agent receives only the index file, no actual docs to read | Isolates index-only value from doc content value |
| **Oracle** | Agent receives the exact relevant docs pre-selected in context | Upper bound: best-case with perfect retrieval |
| **Length-matched random** | Agent receives random docs of the same total token count | Controls for "more tokens = better" confound |

Baselines run once per axis, not per variant, to limit cost. If a variant fails to beat no-index on any metric, flag it as a critical failure.

### Eval Axes (Sequential with Beam Search)

Each axis varies one dimension while holding others at their defaults (see Defaults Table below). Results cascade via beam search—the top 2-3 candidates (not just the winner) advance to the next axis. This prevents greedy selection from missing global optima.

**Beam search protocol:**
- After each axis, retain all candidates within statistical parity of the leader (pairwise Wilcoxon p > 0.10—a lenient screening threshold). This replaces the arbitrary "within 2 points" rule.
- Typical beam width: 2-4 candidates per axis, depending on variance
- Each subsequent axis tests variants against all retained prior candidates
- Search space remains manageable: ~3 × variants_per_axis per axis, not exponential

**Axis ordering — pilot study protocol:**
- Before full eval, run a lightweight pilot: 10 tasks, N=3 repetitions
- Test two alternative orderings for sensitivity
- If orderings produce different winners, expand interaction validation
- Default ordering follows dependency logic: structure before metadata, format before position

**Interaction validation protocol:**
- After all 10 axes, take the top 2 candidates from axes 1-5 (the most impactful)
- Use a 2^(5-1) Resolution V fractional factorial design (16 runs). This optimally estimates all main effects and two-way interactions for 5 binary factors. Generator: E = ABCD.
- Alternative: if budget allows, run full 2^5 = 32 configurations for complete interaction estimation
- Pre-register pruning criteria (e.g., "YAML + flat structure excluded—YAML requires hierarchy")
- If any factorial combination scores significantly above the sequential winner (p < 0.05), it overrides the sequential result
- Use Lenth method or half-normal plots to identify significant interactions

**Defaults for non-varied dimensions:**

| Dimension | Default Value | Rationale |
|-----------|---------------|-----------|
| Structure | 3-tier | Matches common AGENTS.md practice |
| Pointer metadata | path-only | Minimal baseline |
| Format | markdown-list | Widely used, moderate token cost |
| Position | BLUF | Good information architecture default |
| Doc transformation | Passthrough | No processing, pure baseline |
| Index scale | 15 entries | Matches fixture domain size |
| Signal-to-noise | 0% distractors | Clean baseline |
| Entry granularity | file-level | Standard convention |
| Cross-reference density | none | Simplest configuration |
| Temporal markers | none | Simplest configuration |

**Axis definitions:**

| # | Axis | Variants | Tests |
|---|------|----------|-------|
| 1 | Structure | flat, 2-tier, 3-tier, 4-tier, inline-required | Does tiering help? Does inlining required content help? |
| 2 | Pointer metadata | path-only, +summary, +tokens, +related | Does metadata justify extra tokens? |
| 3 | Format family | pipe-delimited, YAML, markdown-list, markdown-table, plain-markdown | Which serialization do LLMs comprehend best? |
| 4 | Position strategy | natural, BLUF, edges, random | Does ordering matter at index scale? |
| 5 | Doc transformation | passthrough, algorithmic, LLM-compressed, restructured, tagged | Which transformation helps most per token? |
| 6 | Index scale | 5, 15, 50, 100, 200 entries | How does entry count affect retrieval/efficiency? |
| 7 | Signal-to-noise | 0%, 25%, 50%, 75% distractor entries | How robust is retrieval with irrelevant entries? |
| 8 | Entry granularity | file-level, section-level, function-level, mixed | Does pointing to finer-grained units help? |
| 9 | Cross-reference density | none, light (related field), dense (bidirectional links) | Do cross-references aid multi-hop tasks? |
| 10 | Temporal markers | none, version tags, last-modified dates, deprecation warnings | Do temporal signals prevent stale information use? |
| V | Interaction validation | Top 2-3 from each axis, factorial | Do axes interact? Is the sequential winner the global winner? |

~30-40 variants across sequential axes + ~16-24 factorial validation variants.

**Axis notes:**
- **Axis 6 (Scale):** Variants add entries from same domains + new domains. Measures how steeply performance degrades.
- **Axis 7 (Noise):** Distractor entries are irrelevant to any test task. Measures precision under noise and wasted tokens.
- **Axis 8 (Granularity):** Focuses on what entries POINT TO (file vs section vs function), not chunking algorithm. Research shows chunk size dominates over strategy at the same size (somasays/rag-experiments; see also arXiv 2505.21700 "Rethinking Chunk Size for Long-Document Retrieval").
- **Axis 9 (Cross-refs):** Light = one-directional `related` fields. Dense = bidirectional links with relationship types.
- **Axis 10 (Temporal):** Examples: "Added in v3.2", "Last modified: 2026-01-15", "Deprecated: use X instead".

### Task Types

11 task types with empirical weights. Minimum 30 tasks per type, 330+ tasks total. Weights derive from production frequency, failure criticality, and difficulty calibration (see `planning/research/task-weights.md` for sources).

| # | Task Type | Weight | Description |
|---|-----------|--------|-------------|
| 1 | **Retrieval** | 0.15 | "Which file answers this question?" F-beta (beta=2), weighting recall over precision. Missing a needed doc costs more than including an extra. Secondary: Recall@K. |
| 2 | **Fact extraction** | 0.15 | "What does this API do?" Given index + doc content, answer factual questions. Primary: LLM-as-judge with rubric. Secondary: keyword matching with aliases. |
| 3 | **Code generation** | 0.15 | "Write code using this API." Primary: deterministic test suite (regex patterns + forbidden anti-patterns). Secondary: LLM-as-judge (API usage, error handling, conventions). Reports disagreement rate. |
| 4 | **End-to-end agentic** | 0.12 | Agent receives a coding problem with tool-call access to the index. Scored on: retrieval invocation, file selection, output correctness. Captures the 56% skill-non-invocation failure mode (Vercel research). |
| 5 | **Multi-hop reasoning** | 0.10 | Requires combining 2-3 documents to answer. Tests cross-document reasoning. Accuracy drops 25-30 points vs single-hop (HotpotQA, MuSiQue data). |
| 6 | **Negative / unanswerable** | 0.08 | Questions unanswerable from the index. Correct response: explicit abstention ("not in available documentation"). Critical: reasoning-tuned models show 24% worse abstention (AbstentionBench). |
| 7 | **Compositional code gen** | 0.07 | Requires combining multiple APIs/patterns from different docs. Error rates compound like multi-hop. Tests multi-file coding. |
| 8 | **Robustness / perturbation** | 0.06 | Retrieval/fact extraction tasks with typos, synonyms, paraphrases, or informal query phrasing. Measures degradation. Up to 40pp degradation in enterprise benchmarks. |
| 9 | **Disambiguation** | 0.05 | Queries matching multiple entries (e.g., "the auth module" when client and server auth both exist). Correct response: clarify or list options—never guess. |
| 10 | **Conflicting information** | 0.04 | Index contains contradictory entries (e.g., v2 docs say X, v3 docs say Y). Correct response: identify the conflict, prefer newer/authoritative source, or flag it. |
| 11 | **Efficiency-constrained** | 0.03 | Standard tasks with token budget constraints. Agent must retrieve and answer within N tool-call tokens. Tests whether index format enables efficient retrieval. |

**Weight sensitivity analysis:** Report results under default, retrieval-heavy (+0.05 to types 1-2, -0.05 from types 9-11), and code-heavy (+0.05 to types 3, 7; -0.05 from types 5-6) schemes. If the winner changes, report fragility.

### Metrics

**Primary metrics per task type:**

| Task Type | Primary Metric | Secondary Metric |
|-----------|---------------|------------------|
| Retrieval | F-beta (beta=2) | Recall@K, MRR |
| Fact extraction | LLM-judge accuracy | Keyword match accuracy |
| Code generation | Test pass rate | LLM-judge quality score |
| End-to-end agentic | Composite (retrieval + correctness) | Tool invocation rate |
| Multi-hop | Answer correctness | Retrieval completeness |
| Negative/unanswerable | Correct abstention rate | False positive rate |
| Compositional code gen | Test pass rate | API coverage |
| Robustness | Delta from clean baseline | Degradation curve |
| Disambiguation | Appropriate response rate | Clarification quality |
| Conflicting info | Conflict identification rate | Source preference accuracy |
| Efficiency-constrained | Score within budget | Token utilization ratio |

**Cross-cutting metrics (computed for all task types):**

| Metric | Description |
|--------|-------------|
| **Faithfulness** | Fraction of claims supported by retrieved docs. NLI-based: decompose response into claims, verify each against context. Adapted from RAGAS. |
| **Tool call count** | File reads/searches per task. Lower is better at equal quality. |
| **First-attempt success** | Fraction correct on first response, no revision. |
| **Correct abstention** | On unanswerable: fraction abstaining. On answerable: fraction not abstaining. Both matter. |
| **Navigation path quality** | For agentic tasks: actual vs. optimal file-read sequence. Penalizes backtracking. |
| **Consistency** | Pairwise semantic similarity across N repetitions. High variance suggests weak index. |

**Composite score:**

```
composite = sum(weight_i × score_i) for i in 1..11 task types
```

Each `score_i` is the mean across tasks of that type (0-1 normalized). The composite is one number per variant per model, used for ranking.

**Token efficiency metrics:**

| Metric | Formula |
|--------|---------|
| Information density | composite / 1000 index tokens |
| Efficiency ratio | composite / (index tokens / baseline tokens) |
| Marginal cost | delta tokens / delta composite |

### Scoring Protocol

**LLM-as-judge scores fact extraction and code generation quality.** Keyword matching and regex patterns calibrate as secondary scorers. The LLM judge uses structured rubrics with explicit 1-5 criteria.

```yaml
# Example fact extraction rubric
criteria:
  - name: correctness
    weight: 0.6
    scale: "1=wrong, 2=partially correct, 3=correct but imprecise, 4=correct, 5=correct with nuance"
  - name: completeness
    weight: 0.3
    scale: "1=missing key facts, 3=main facts present, 5=comprehensive"
  - name: conciseness
    weight: 0.1
    scale: "1=excessive padding, 3=reasonable, 5=minimal and precise"
```

**Scorer validation:**
- 30-50 gold examples per task type (330-550 total)
- Gold standard spans difficulty: easy, medium, hard, edge cases
- Inter-annotator agreement on 20% overlap (two annotators per item)
- LLM-judge calibrated to gold standard; target: Cohen's kappa >= 0.70 (substantial agreement, Landis-Koch)
- Canary tasks with trivial answers verify the scoring pipeline end-to-end
- Report LLM-judge vs. deterministic scorer disagreement rate per task type

**Scorer disagreement resolution:**
- When LLM-judge and deterministic scorer disagree, gold standard breaks ties
- Log and analyze systematic disagreement patterns (e.g., "LLM-judge scores regex-matching code higher")
- If disagreement exceeds 15% on a task type, revise and recalibrate the rubric

**Grade outcomes, not paths.** Evaluate what the agent produced, not its step sequence. Two agents producing identical outputs receive identical scores—whether one read 3 files or 7. Path metrics (tool call count, navigation quality) track efficiency, not correctness.

### LLM-as-Judge Configuration

**Judge model selection:** The judge must differ in model family from the evaluated model. Self-preference bias inflates scores when a model judges its own output. Default judge: GPT-4o via OpenRouter. If evaluating GPT-4o, use Claude Sonnet 4.5.

**Panel of LLM evaluators (PoLL):** For final comparison (Phase 7), use a 3-model panel: GPT-4o-mini + Claude 4.5 Haiku + Gemini 3 Flash. Aggregate by averaging. Panels of smaller models outperform a single GPT-4 judge at 7-8x lower cost (Verga et al., 2024).

**Two-tier evaluation:** Use GPT-4o-mini (~$0.15/M tokens) for routine runs. Use GPT-4o or PoLL for validation and regression investigation. Verify cheaper model scores correlate with frontier model (target: Spearman >= 0.80).

**Bias prevention:**
- Pointwise scoring (single-answer rubric), not pairwise—avoids position bias
- Chain-of-thought prompting: judge explains reasoning before scoring—improves alignment
- Temperature 0.0 for deterministic output
- Rubric penalizes verbosity—prevents verbosity bias
- For code: augment LLM judge with test execution (~42% agreement without, ~72% with—Findeis et al. 2025; He et al. arXiv 2503.02246)

**Calibration targets:**
- Cohen's kappa >= 0.70 (substantial, Landis-Koch 0.61-0.80) between judge and gold standard
- Spearman rho >= 0.80 (very strong) on score ordering
- Kendall's tau alongside Spearman (more robust to ties)
- 150+ human-annotated examples for judge validation (60 for rubric iteration, 150+ for production)

### Prompt Framing

Two framing strategies tested in the pilot study:

- **Constant:** Same system prompt regardless of variant. Only index content changes. Isolates index effect.
- **Adapted:** System prompt includes variant-specific guidance (e.g., "The index uses YAML format..."). Tests whether explanation improves comprehension.

If one consistently outperforms, it becomes default. If mixed, report both per axis.

### LLM Providers

Uses [LiteLLM](https://github.com/BerriAI/litellm) for unified provider access via native SDKs. **OpenRouter** is the primary provider—one API key accesses 400+ models across major providers.

```python
import litellm
import os

response = litellm.completion(
    model="openrouter/anthropic/claude-opus-4.5",  # Note: dot before 5, not hyphen
    messages=[...],
    api_key=os.environ["OPENROUTER_API_KEY"],
    extra_body={
        "provider": {
            "order": ["Anthropic"],  # Capitalize provider names
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny"  # No data retention
        }
    }
)
```

**Provider pinning options:**
- `order` + `allow_fallbacks: false` ensures single-provider routing
- Alternative: `only: ["Anthropic"]` states intent explicitly (may be more reliable)
- `require_parameters: true` ensures provider supports all parameters (temperature, seed)
- `data_collection: "deny"` routes only to providers not collecting/storing data

**Generation metadata:** The response includes a generation ID. Query `GET /api/v1/generation?id={generation_id}` for provider, model, latency, tokens, and cost.

**Minimum model coverage:** Results must generalize across 3+ models from different providers:

| Tier | Example Models | Purpose |
|------|---------------|---------|
| Frontier | Claude Opus 4.5, GPT-5.2 Pro, Gemini 3 Pro | Best-case performance ceiling |
| Mid-tier | GPT-5.2, Mistral Large 3, DeepSeek V3.2 | Practical performance at lower cost |
| Small | Ministral 3 8B, Devstral 2 | Floor performance; cost-sensitive users |

If optimal variant differs by tier, report tier-specific recommendations. The cross-model winner must be statistically best (or statistically tied) on all tested models.

**Privacy:** Set `data_collection: "deny"` in provider object for all eval workloads (see above).

### Cost Estimation

Cost estimation is **token-based, not per-API-call.** Models charge different rates per token, and token counts vary by variant.

```python
cost = (prompt_tokens * input_price_per_token) + (completion_tokens * output_price_per_token)
```

**Reported per axis:**
- Total axis cost (all variants × tasks × N repetitions)
- Cost per variant per task (mean, median, max)
- Cost breakdown: prompt tokens vs completion tokens
- Incremental cost: how much does adding this axis to the eval suite cost?

**Budget guardrails:**
- Pre-run cost estimate (based on token counts)
- Per-axis budget cap with `--max-cost-per-axis` flag
- Live cost tracker during execution
- Automatic pause if projected cost exceeds budget by 2x

### Infrastructure & Process

**Qualitative error analysis protocol:**
- After each axis, review 10-15 failures per task type
- Categorize failures: retrieval miss, extraction error, hallucination, format confusion, other
- Log categories in JSON alongside raw results
- Failure categories guide variant and rubric improvements
- Pattern: "3 of 5 retrieval failures on YAML variant involved nested entries" → actionable

**Transcript review protocol:**
- For agentic tasks, save full transcripts (all turns, tool calls, responses)
- Review 20% of transcripts per variant to identify patterns
- Look for: unnecessary backtracking, incorrect file selection rationale, missed tool calls
- Transcript review calibrates navigation path scoring

**Eval saturation monitoring:**
- Track cumulative composite score as tasks accumulate
- Plot learning curve: score stability vs task count
- If the last 10% of tasks changes no rankings, the eval is saturated
- Target: rankings stable within 1 point of composite score over last 20% of tasks
- Report saturation point per axis

**Sentinel tasks for temporal drift:**
- Run 5-10 fixed sentinel tasks at session start and end
- Sentinels are trivially easy (known answers, deterministic scoring)
- If sentinel scores drift >5% within a session, flag possible API behavior change
- Compare sentinel baselines across sessions to detect model or provider changes
- Sentinel results excluded from main analysis

**Contamination prevention:**
- Task sets are private — not published publicly
- Tasks use synthetic project structures, not real repos that may be in training data
- For tasks from public benchmarks (HotpotQA, Natural Questions): paraphrase queries and verify they produce the same answer
- Periodically test zero-shot accuracy (no index) as a contamination check
- Replace any task with >80% zero-shot accuracy (compromised)
- Version-pin model IDs (not aliases) to avoid silent model updates

### Fixture Domains

1. **Framework API docs** — 15-25 files from real framework docs. Tests lookup-heavy knowledge: function signatures, parameters, code examples, migration guides.
2. **Project repo docs** — Synthetic but realistic: architecture decisions, setup guides, conventions, contribution guidelines. Tests contextual knowledge.
3. **Skills/workflows** — Procedural: deploy, test, debug, onboard. Tests step-by-step procedures with conditional paths.

**Task count:** 330+ tasks (30+ per type × 11 types). Distribution:
- Framework API: ~40% of tasks (retrieval-heavy, code-gen-heavy)
- Project repo: ~35% of tasks (fact-extraction-heavy, disambiguation-heavy)
- Skills/workflows: ~25% of tasks (agentic-heavy, multi-hop-heavy)

**Primary dataset sources per task type** (full details in `planning/research/datasets.md`):

| Task Type | Primary Dataset | HF ID | License |
|-----------|----------------|-------|---------|
| Retrieval | CodeRAG-Bench lib-docs | `code-rag-bench/library-documentation` | CC-BY-SA-4.0 |
| Fact Extraction | IBM TechQA | `PrimeQA/TechQA` | Apache-2.0 |
| Code Generation | CodeRAG-Bench/DS-1000 | `code-rag-bench/ds1000` | CC-BY-SA-4.0 |
| End-to-End Agentic | SWE-bench Verified | `princeton-nlp/SWE-bench_Verified`[^1] | MIT (code) |
| Multi-Hop Reasoning | MultiHop-RAG | `yixuantt/MultiHopRAG` | ODC-BY |
| Negative/Unanswerable | RepLiQA | `ServiceNow/repliqa` | CC-BY-4.0 |
| Compositional Code Gen | BigCodeBench | `bigcode/bigcodebench` | Apache-2.0 |
| Robustness | PromptBench + TextAttack | generators (pip) | MIT |
| Disambiguation | AmbigQA | `sewon/ambig_qa` | CC-BY-SA-3.0 |
| Conflicting Info | WikiContradict[^2] | `ibm-research/Wikipedia_contradict_benchmark` | MIT |
| Efficiency-Constrained | N/A — methodology from token-economy papers | -- | -- |

Cross-cutting: RAGBench (`galileo-ai/ragbench`, 100K examples, CC-BY-4.0) for multi-task RAG eval; RAGAS for synthetic test generation from documentation.

[^1]: SWE-bench codebase is MIT-licensed; dataset content is sourced from open-source GitHub repos with their own licenses. No explicit dataset-level license declared on HF. Also available at `SWE-bench/SWE-bench_Verified`.
[^2]: WikiContradict has only 253 examples. Augment with synthetic version conflicts + ConflictBank temporal subset to reach 30+ tasks.

**Robustness generators note:** nlpaug removed (abandoned July 2022). Use PromptBench (Microsoft, MIT) for character/word/sentence/semantic perturbations + TextAttack's `augmentation.Augmenter` for additional attack recipes. Pin TextAttack to v0.3.10.

### Response Caching

Disk cache keyed on `SHA-256(model_version + temperature + max_tokens + system_prompt + full_messages)`. Use explicit model versions (not aliases) to avoid drift.

- `--no-cache` flag forces fresh runs
- `--cache-ttl` option (default: 30 days)
- LRU eviction with configurable cache size
- `cache_version` integer in key for manual invalidation
- Caching disabled across repetitions within a run to capture variance

### Eval Runner CLI

```bash
# Run all tasks on all variants for a specific axis
agent-evals run --axis 1 --model openrouter/anthropic/claude-sonnet-4.5

# Run a subset of task types with a specific variant
agent-evals run --tasks retrieval,fact_extraction --variant yaml-with-summaries

# Limit to N samples for quick iteration
agent-evals run --axis 1 --limit 10

# Debug a specific task
agent-evals run --task-id retrieval_042 --variant markdown-tiered

# Dry run: enumerate tasks, estimate tokens, print projected cost
agent-evals run --axis 1 --dry-run

# Resume a failed run (reuses completed samples)
agent-evals retry <log-file>

# Re-run only failures from a previous run
agent-evals run --filter-failing <log-file>
```

**Key flags:**

| Flag | Description |
|------|-------------|
| `--axis N` | Run all variants for eval axis N (1-10) |
| `--tasks type1,type2` | Filter to specific task types |
| `--task-id ID` | Run a single task (for debugging) |
| `--variant NAME` | Run a single variant (for debugging) |
| `--model provider/name` | LLM model (default: from config) |
| `--model-config file.yaml` | Model-specific args |
| `--limit N` | Max tasks per type (for quick iteration) |
| `--repetitions N` | Override repetition count (default: 10) |
| `--temperature F` | Override temperature (default: 0.3) |
| `--max-connections N` | Concurrent API connections (default: 10) |
| `--max-tasks N` | Parallel task evaluation (default: 1) |
| `--dry-run` | Estimate tokens and cost without API calls |
| `--max-cost DOLLARS` | Budget cap; pause if projected cost exceeds 2x |
| `--output-dir DIR` | Results directory (default: `reports/`) |
| `--output-format json\|csv` | Output format (default: json) |
| `--no-cache` | Force fresh LLM calls |
| `--display rich\|plain\|none` | Progress display mode |
| `--judge-model provider/name` | Override judge model (default: GPT-4o) |

**Config file:** `eval-config.yaml` sets defaults. CLI flags override config; environment variables (`AGENT_EVALS_` prefix) also supported. Precedence: CLI > env vars > config file.

```yaml
# eval-config.yaml
model: openrouter/anthropic/claude-sonnet-4.5  # Note: dot before 5
judge_model: openrouter/openai/gpt-4o
repetitions: 10
temperature: 0.3
max_connections: 10
output_dir: ./reports
```

### Outputs

- Console table ranked by composite score, with efficiency metrics and significance flags
- JSON with all raw trials for custom analysis
- Per-axis summary showing winners, effect sizes, and sensitivity analysis
- Interaction-effect validation report
- Cost report per axis, per variant, per model
- Error analysis summary with failure categorization
- Saturation analysis plots
- Sentinel task drift report

---

## UX: Four Ways to Start

**Quick mode** — CLI flags only:
```bash
agent-index --local ./docs --name "My Project"
```

**Auto-detect** — Scans the project and proposes a tiered config:
```bash
agent-index --auto-detect
```
Heuristics assign files to tiers by name ("getting-started" → required, API reference → recommended, remainder → reference). The user then reviews and edits the generated YAML.

**Interactive wizard** — Guided questionnaire:
```bash
agent-index --init
```
Prompts for project name, doc locations, tier assignments, commands, and boundary rules, then produces a complete `agent-index.yaml`.

**Scaffold** — Creates the recommended directory structure with templates:
```bash
agent-index --scaffold
```
Generates placeholder `.llms.md` files for each tier.

All modes use the same `agent-index.yaml` format (YAML primary, TOML secondary).

---

## Additional Features

**CI validation (`--validate`)** — Compares the generated index against actual docs using content hashes. Reports missing files, extra files, and stale entries. Returns non-zero exit code on drift. Includes a `pre-commit` hook definition (`.pre-commit-hooks.yaml`).

**Token estimation** — Estimates token counts via LiteLLM's `token_counter(model, text)`, which dispatches to the model-appropriate tokenizer. Falls back to a ~4 chars/token heuristic offline. Note: tiktoken provides accurate counts only for OpenAI models and errs by 10-20% for others. Displays counts in index metadata and warns if totals exceed the recommended 5-10K token budget.

**Multi-index** — Generates multiple indexes from one config (e.g., one per monorepo package). Each index receives its own marker pair for injection.

---

## Research References

This design incorporates findings from RESEARCH.md and the following sources:

| Source | Key Finding | Informs |
|--------|------------|---------|
| arXiv 2601.20404 (Jan 2026) | 28.64% median runtime reduction with AGENTS.md present (vs. absent) | Value of any index file |
| arXiv 2411.10541 (Nov 2024) | Up to 40% variance by format; cross-model IoU < 0.2 | Format axis, multi-model testing |
| arXiv 2601.17087 (Jan 2026) | Simulated users underestimate hard tasks (ECE 15.1) | End-to-end agentic tasks |
| ShortenDoc (2025) | Compression degrades code gen beyond 10% | Transformation axis |
| SWE-Pruner (arXiv 2601.16746) | Agent tokens: 76% read, 12% execute, 12% edit | Retrieval weighting |
| AbstentionBench (arXiv 2506.09038) | Reasoning models: 24% worse abstention | Negative/unanswerable tasks |
| Seven Failure Points (arXiv 2401.05856) | 3 retrieval + 4 generation failure modes | Error analysis categories |
| AgentBench (ICLR 2024) | Reciprocal-average weighting (1/mean_score) gives harder tasks more weight | Rationale for difficulty-calibrated weights (not the formula used) |
| RAGAS (arXiv 2309.15217) | NLI-based claim decomposition for faithfulness | Faithfulness metric (equal weighting is library default, not paper finding) |
| somasays/rag-experiments + arXiv 2505.21700 | Chunk size dominates over strategy at same size | Axis 8 (granularity) |
| Findeis et al. 2025 (via arXiv 2503.02246) | LLM judges: 42% accuracy on code; 72% with execution | Code correctness scoring |

---

## Implementation Phases

| Phase | What | Depends On |
|-------|------|------------|
| 1 | Package scaffolding, code migration, Pydantic models, tests | Nothing |
| 2 | Eval framework core: variants, tasks (11 types), runner, LiteLLM/OpenRouter client, cache, fixtures, metrics, baselines | Parallel with Phase 1 |
| 3 | Gold standard: 30-50 human-labeled examples per task type, scorer calibration, sentinel tasks | Phase 2 |
| 4 | Pilot study: axis-ordering sensitivity, prompt-framing comparison, saturation check | Phase 3 |
| 5 | First eval axes: structure, metadata, format, position (axes 1-4) with beam search | Phase 4 results |
| 6 | Second eval axes: transformation, scale, noise, granularity, cross-ref, temporal (axes 5-10) | Phase 5 results |
| 7 | Interaction validation: factorial design of top candidates across all axes | Phase 6 results |
| 8 | Organizer tier system using winning format, cross-tool output | Phase 7 results |
| 9 | Doc transformation pipeline + transformation eval axis refinement | Phase 8 |
| 10 | UX: auto-detect, wizard, scaffold, CI validation, pre-commit hook | Phase 8 |

Phases 1 and 2 run in parallel. Phase 3 produces the gold standard for scorer calibration. Phase 4 validates methodology before the full eval. Each subsequent phase builds on prior results.
