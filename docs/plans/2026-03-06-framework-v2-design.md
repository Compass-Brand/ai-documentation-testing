# Framework v2 Design: End-to-End AI Documentation Testing

**Date:** 2026-03-06
**Status:** Draft
**Authors:** Trevor Leigh, Claude Opus 4.6

## Vision

Answer the question: **"How should I structure my documentation so AI agents perform best?"** — with proof, across models, across context delivery methods, measuring what production systems care about.

## Audiences (priority order)

1. **Documentation authors** — actionable recommendations ("use 2-tier markdown with summaries")
2. **Agent builders** — operational tradeoffs (cost, latency, stability per strategy)
3. **Researchers** — statistical evidence backing every claim

Caveat: all findings must be provable. Researcher-grade rigor under the hood; doc-author-friendly output on top.

## Unique Position

No existing benchmark (SWE-bench, GAIA, Tau-bench, WebArena, AgentBench) tests how documentation format affects agent performance. This framework fills that gap with:

- 10 format axes × 47 variants testing documentation structure
- Multiple context delivery strategies testing how docs reach the agent
- Taguchi DOE for efficient statistical screening
- Cross-strategy meta-analysis showing where optimal format differs by delivery method

## Current State

The framework has 355 gold tasks across 11 types, 47 variants across 10 axes, 4 context strategies (full_context, system_prompt, rag, tool_based), Taguchi L50 screening with ANOVA, and cross-strategy comparison via Kendall's W and Friedman test.

**What's missing:**

| Gap | Status |
|-----|--------|
| Real-world datasets (9 adapters) | Implemented on stranded branch `fix/unit-12-dataset-integration` |
| LLM-as-judge + PoLL scoring | Implemented on stranded branch |
| Operational metrics (cost, latency, stability) | Not started |
| MCP-native strategy | Not started |
| Compression strategy | Not started |
| Tool description axis | Not started |
| Agent instruction file axis | Not started |
| Hallucination detection | Not started |
| Multi-session persistence testing | Not started |
| KV-cache friendliness tracking | Not started |
| Dynamic tool availability | Not started |

The stranded branch diverged from main (115 commits apart) during the context strategy rewrite and was never rebased.

---

## Phase A: Real Data + Semantic Scoring

**Goal:** Run the existing 10 axes and 4 context strategies against real-world documentation datasets, scored by both programmatic matchers and LLM-as-judge with PoLL validation.

### A1: Dataset Adapter Infrastructure

Cherry-pick from stranded branch: `base.py`, `cache.py`, `_hf_utils.py`, `__init__.py` registry.

The abstract base class defines the right interface:

```python
class DatasetAdapter(ABC):
    def name() -> str
    def hf_dataset_id() -> str | None
    def task_type() -> str
    def domain() -> str
    def license() -> str
    def contamination_risk() -> str
    def convert_tasks(output_dir, limit) -> int
    def build_doc_tree(limit) -> DocTree
```

Auto-discovery via `pkgutil.iter_modules()`. Registry maps names to adapter classes.

### A2: Individual Adapters (9 datasets)

Review case-by-case. Each adapter downloads from HuggingFace, converts to task YAML, and builds a DocTree.

| Dataset | HF ID | Task Type | License | Contamination |
|---------|-------|-----------|---------|---------------|
| IBM TechQA | `PrimeQA/TechQA` | fact_extraction | Apache-2.0 | Low |
| CodeRAG-Bench | `code-rag-bench/library-documentation` | retrieval | CC-BY-SA-4.0 | Moderate |
| CodeRAG-Bench DS-1000 | `code-rag-bench/ds1000` | code_generation | CC-BY-SA-4.0 | Moderate |
| SWE-bench Verified | `princeton-nlp/SWE-bench_Verified` | agentic | MIT | High |
| MultiHop-RAG | `yixuantt/MultiHopRAG` | multi_hop | MIT | Moderate |
| RepLiQA | `ServiceNow/repliqa` | negative | CC-BY-4.0 | Low |
| AmbigQA | `din0s/ambig_qa` | disambiguation | CC-BY-SA-3.0 | High |
| BigCodeBench | `bigcode/bigcodebench` | compositional | Apache-2.0 | Moderate |
| WikiContradict | `ibm-research/Wikipedia_contradict_benchmark` | conflicting | CC-BY-4.0 | High |

Key verification: each adapter's `build_doc_tree()` must populate `rel_path`, `content`, `tier`, and `section` fields so variants can render them. Adapters with datasets that lack natural tier/section mappings should degrade gracefully.

### A3: Source Routing + Mixed-Source Runs

Cherry-pick `source.py` module and adapt to current CLI structure.

- `--source repliqa` loads tasks and DocTree from the RepLiQA adapter
- `--source mixed` interleaves tasks from multiple adapters in a single Taguchi screening (new capability beyond stranded branch)

Mixed-source runs let Taguchi screening measure format effects across documentation domains, not just within one dataset.

### A4: Judge Module

Cherry-pick `judge/calibrator.py` and `judge/poll.py`. Wire into runner as a validation signal.

**Two modes:**

- **Routine** — Single model (GPT-5-mini) scores a configurable sample of trials alongside programmatic scoring. Default 5% sample rate.
- **PoLL** — 3-model panel (GPT-5-mini, Claude Haiku 4.5, Gemini 2.5 Flash) for validation runs. Panels of smaller models outperform single large judges at 7-8x lower cost (Verga et al., 2024).

**Integration with runner:**

```
Trial flow:
  prompt -> LLM -> response -> programmatic_score --+--> TrialResult
                            \-> judge_score (N%) ----/
```

Judge scores stored as a separate field on `TrialResult`, not replacing programmatic scores. In Phase A, judge scores serve as validation only — they verify programmatic rankings are correct.

**Calibration targets:** Cohen's kappa >= 0.70, Spearman rho >= 0.80, minimum 30 gold examples per task type.

**Configuration:**

```yaml
judge:
  enabled: true
  sample_rate: 0.05
  mode: routine
  routine_model: openrouter/openai/gpt-5-mini
  poll_panel:
    - openrouter/openai/gpt-5-mini
    - openrouter/anthropic/claude-haiku-4.5
    - openrouter/google/gemini-2.5-flash
  calibration_threshold:
    cohens_kappa: 0.70
    spearman_rho: 0.80
```

### A5: Recommendations Report Layer

Render Taguchi findings as plain-language recommendations for documentation authors, backed by statistical evidence.

**Per-factor finding:**

```
FINDING: Documentation hierarchy depth
  Best:  2-tier structure
  Worst: flat (no hierarchy)
  Effect size: +12.3 points composite score (95% CI: [8.1, 16.5])
  Consistent across strategies: yes (3/4 strategies agree)

  Recommendation: Use two levels of hierarchy (sections -> pages).
  Adding a third level provides no measurable benefit.
  Removing hierarchy entirely drops performance significantly.
```

**Per-strategy breakdown (for agent builders):**

```
STRATEGY COMPARISON: Documentation hierarchy depth
  full_context:    2-tier wins (+14.1 pts)
  system_prompt:   2-tier wins (+11.8 pts)
  rag:             3-tier wins (+9.2 pts)    <- differs
  tool_based:      2-tier wins (+13.0 pts)

  Note: RAG benefits from deeper granularity because more
  hierarchy creates better chunk boundaries.
```

Statistical proof (ANOVA tables, confidence intervals, effect sizes) lives in a separate "evidence" section.

### Phase A Exit Criteria

- All 9 dataset adapters produce valid DocTree + TaskDefinition objects
- `--source repliqa` (or any adapter) runs a full Taguchi screening with all 4 context strategies
- Judge scores stored alongside programmatic scores at configurable sample rate
- Report includes plain-language recommendations backed by statistical evidence
- Cross-strategy comparison shows where optimal format differs by delivery method

### Phase A Does NOT Include

- No new axes or strategies
- Judge scores are validation-only, not factored into composite
- No operational metrics beyond accuracy
- No AGENTS.md or tool description testing

---

## Phase B: Operational Metrics

**Goal:** Every trial captures Cost, Latency, Accuracy, Security, and Stability — so findings aren't just "this format scores higher" but "this format scores higher AND costs less AND is more consistent."

### Data Sources: OpenRouter API

Two access patterns, both leveraging OpenRouter's response metadata:

**Inline (from every response, zero extra API calls):**

| Field | Source |
|-------|--------|
| `usage.prompt_tokens` | Response body |
| `usage.completion_tokens` | Response body |
| `usage.cost` | Response body — actual USD charged |
| `usage.prompt_tokens_details.cached_tokens` | Response body |
| `usage.prompt_tokens_details.cache_write_tokens` | Response body |
| `usage.completion_tokens_details.reasoning_tokens` | Response body |
| `provider` | Response body — which provider served it |
| `id` | Response body — generation ID for post-hoc lookup |

**Post-hoc (via `GET /api/v1/generation?id=gen-XXX`, one call per trial):**

| Field | Description |
|-------|-------------|
| `latency` | Total latency in ms |
| `generation_time` | Generation duration in ms |
| `moderation_latency` | Moderation processing time in ms |
| `cache_discount` | USD savings from prompt caching |
| `native_tokens_cached` | Provider-reported cached tokens |
| `native_tokens_reasoning` | Reasoning/thinking tokens |
| `provider_responses[]` | Every provider attempt with per-attempt latency and status |
| `streamed` | Whether response was streamed |

**LiteLLM note:** LiteLLM merged PR #15448 (Oct 2025) to extract cost from OpenRouter responses. Known streaming cost bug (issue #16021) — use non-streaming for evaluation runs.

### B1: Inline Metadata Capture

Extract full `usage` object, `provider`, and `id` from every LLM response. Verify LiteLLM passes through `prompt_tokens_details` and `completion_tokens_details`.

### B2: Generation Stats Fetcher

Call `/api/v1/generation?id=gen-XXX` after each trial for latency, cache discount, and provider routing data. Configurable sample rate (default 100% — it's a single GET, not an LLM call).

### B3: CostMetrics Data Model

```python
@dataclass
class CostMetrics:
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    total_cost_usd: float
    cache_discount_usd: float | None
    latency_ms: float | None
    generation_time_ms: float | None
    provider: str
    generation_id: str
    turns: list[TurnMetrics] | None  # For tool_based: per-turn breakdown
```

Stored as a field on `TrialResult`. For tool_based strategy, accumulate inline data per turn and fetch generation stats for each turn.

### B4: Provider Fallback Detection

The `provider_responses` array from generation stats shows every provider attempt during routing, including failures. Flag trials where OpenRouter retried across providers — routing instability affects latency and potentially results. Annotate these trials; optionally exclude from stability analysis.

### B5: Stability Metrics

Measure consistency across repeated runs:

- **Coefficient of variation** — std_dev / mean across reps per trial group
- **Min/max spread** — worst vs best score across reps
- **Per-strategy stability comparison** — "tool_based is 3x less stable than full_context"
- **Provider stability** — do results change when OpenRouter routes to different providers?

### B6: Cost-Efficiency Reporting

The key output for documentation authors and agent builders:

```
FORMAT              ACCURACY    COST/TRIAL    CACHE HIT    VARIANCE    EFFICIENCY
2-tier markdown     82.3%       $0.0041       40%          3%          Pareto optimal
3-tier yaml         84.1%       $0.0089       28%          5%          Marginal gain, 2x cost
flat markdown       71.2%       $0.0028       45%          2%          Cheap but weak
oracle              91.0%       $0.0052       35%          1%          Upper bound
```

Pareto frontier plots showing the cost-accuracy tradeoff per strategy.

### B7: Judge Score Graduation

Factor judge scores into composite scoring for task types where calibration passes thresholds (kappa >= 0.70, Spearman >= 0.80). Controlled by config flag. Enables graduating specific task types from programmatic to semantic scoring.

### B8: Security Flags

Annotate trials on relevant task types:

- Agent leaks documentation content that shouldn't appear in responses
- Agent follows injection patterns embedded in documentation
- Agent hallucinates beyond source material

Lighter dimension — captured as flags on existing task types rather than a full separate metric.

### Phase B Exit Criteria

- Every trial stores actual USD cost, token breakdown (including cache/reasoning), latency, and provider from OpenRouter
- Provider fallbacks detected and flagged
- Stability metrics reported per variant x strategy x task type
- Cost-efficiency Pareto frontiers in reports
- Doc author output: "2-tier markdown: 82% accuracy, $0.004/trial, 3% variance, 40% cache hit rate"

### Phase B Does NOT Include

- No new axes or strategies
- No new context delivery methods
- No multi-session testing

---

## Phase C: Modern Agent Patterns

**Goal:** Test how agents work today — MCP discovery, compressed context, dynamic tool sets, instruction file formats, and multi-session persistence.

### New Strategies

#### C1: MCP-Native Strategy

Models the MCP interaction pattern where documentation is exposed as discrete resources with metadata.

- Docs exposed as MCP Resources (passive, fetchable by URI)
- Agent has `list_resources()` and `read_resource(uri)` tools
- Key difference from tool_based: the agent sees a **catalog of described resources** upfront (like MCP tool definitions consuming ~14.3K tokens per server), then selectively fetches content
- Tests whether resource metadata helps the agent fetch the right content, and how description overhead affects performance

Architecturally similar to tool_based but with a critical difference: browsing a library catalog vs. scanning shelf labels.

#### C2: Compression Strategy

Tests whether compressed documentation maintains agent performance at lower cost.

- Takes the variant-rendered output and applies compression before injection
- Sub-strategies:
  - **LLM-summarized** — cheap model summarizes documentation before injection
  - **Algorithmic** — LLMLingua-style token pruning
  - **Format conversion** — Markdown to TOON for structured data (39.6% fewer tokens, comparable accuracy)
- Measures the compression-accuracy tradeoff directly
- Pairs with Phase B cost metrics: "60% compression, 3% accuracy loss, 58% cost reduction"

### New Axes

#### C3: Tool Description Axis

Anthropic achieved SOTA on SWE-bench Verified primarily through refined tool descriptions, not model changes. This axis varies tool description quality and tool set size.

**Description quality levels:**

| Level | Description |
|-------|-------------|
| Minimal | Function name + parameter types only |
| Standard | One-line description + parameter docs |
| Detailed | Multi-line with usage examples, edge cases, when-to-use guidance |
| Adversarial | Deliberately vague or misleading (tests robustness) |

**Tool set size levels:**

| Level | Tools | Purpose |
|-------|-------|---------|
| Core 3 | list_docs, read_doc, search_docs | Current baseline |
| Extended 5 | + get_metadata, list_sections | Richer navigation |
| Extended 7 | + search_by_section, get_related | Targeted retrieval |
| Kitchen sink 10+ | + overlapping/redundant tools | Tests selection accuracy under bloat |

Tests the Tool RAG finding that intelligent retrieval triples accuracy while reducing prompt length by half, and Anthropic's finding that bloated tool sets are a top failure mode.

#### C4: Agent Instruction File Axis

Tests the ETH Zurich finding (arXiv:2602.11988, February 2026) that detailed AGENTS.md files increase inference costs by up to 159% and decrease task success rates.

Three failure modes identified by the study:
1. Unnecessary exploration — instructions cause agents to examine irrelevant code
2. Redundant information — directory trees agents can discover on their own add noise
3. Irrelevant requirements — style guides and deployment workflows loaded into every task

**Verbosity levels:**

| Level | Lines | Content |
|-------|-------|---------|
| None | 0 | No instruction file |
| Minimal | <60 | Non-obvious requirements only (ETH Zurich recommendation) |
| Standard | ~150 | Typical CLAUDE.md/AGENTS.md with conventions and structure |
| Verbose | 300+ | Directory trees, style guides, architecture decisions |
| Overloaded | 500+ | Everything including auto-generated content |

Uniquely valuable because the ETH Zurich study showed the effect but didn't decompose which specific content types help vs. hurt. This framework can.

#### C5: Hallucination Detection

A scoring dimension across all task types, not a standalone axis.

- Compare agent response against actual documentation content provided
- Flag claims not grounded in any source document
- Distinguish: correct extrapolation vs. confident fabrication vs. contradicting source material
- Leverage judge module with a hallucination-specific rubric (standard approach per Google ADK)

Reported as a separate metric: "This format produces 82% accuracy but 15% hallucination rate."

### Strategy Modifiers

#### C6: Multi-Session Persistence Testing

Tests how documentation format survives context compaction.

- Run a multi-turn task sequence where context gets compacted mid-way (simulating Claude Code's automatic compaction)
- Measure: does the agent retain critical documentation knowledge after compaction?
- Hypothesis: structured formats with clear headers survive summarization better than prose
- Architecture: a strategy wrapper that applies simulated compaction between task groups

Not a full multi-session simulation (would require actual agent harness integration), but tests the core question of format durability.

#### C7: Dynamic Tool Availability

Tests the Manus AI pattern of conditionally enabling/disabling tools based on task state.

| Mode | Behavior |
|------|----------|
| Phase-based | Different tools available during "explore" vs "answer" phases |
| Progressive | Start with list_docs only, unlock read_doc after first query, search_docs after second |
| Restricted | Remove search_docs, forcing navigation by structure alone |

Tests whether good documentation structure compensates for fewer tools.

#### C8: KV-Cache Friendliness

Measures how format stability affects caching costs.

- Run the same variant against multiple tasks sequentially
- Track `cached_tokens` and `cache_write_tokens` from OpenRouter
- Formats with stable prefixes achieve higher cache hit rates
- Report: "YAML format achieves 73% cache hit rate vs. 41% for randomized positioning"

Pairs with Phase B cost metrics — cache hits represent the 10x cost multiplier that Manus AI identified as their most important production metric.

### Phase C Exit Criteria

- MCP-native and compression strategies run alongside existing 4 strategies
- Tool description and instruction file axes produce measurable effects in Taguchi screening
- Hallucination rate reported per variant x strategy as a first-class metric
- Multi-session test shows which formats survive compaction
- Cache hit rates tracked and correlated with format characteristics
- Full report answers: "For an MCP-based agent reading compressed docs through dynamic tools, use format X with instruction style Y"

---

## Research References

### Key Studies

- **ETH Zurich AGENTS.md study** (arXiv:2602.11988, Feb 2026) — Detailed instruction files increase inference costs by 159% and decrease task success rates
- **Lost in the Middle** (Liu et al., TACL 2024) — 20-25% accuracy variance based on information position in context; U-shaped performance curve
- **Table format benchmarks** (ImprovingAgents, 2025) — Markdown-KV at 60.7% accuracy vs CSV at 44.3%; 16-point gap from format choice alone
- **Verga et al., 2024** — Panels of smaller LLM judges outperform single large judges at 7-8x lower cost
- **Manus AI context engineering** (2025) — KV-cache hit rate is the most important production metric; 10x cost difference cached vs uncached
- **Anthropic context engineering blog** (Sep 2025) — "Most agent failures are not model failures — they are context failures"
- **Anthropic tool descriptions** (Sep 2025) — SOTA on SWE-bench Verified achieved primarily through refined tool descriptions
- **Tool RAG** (Red Hat, Nov 2025) — Intelligent tool retrieval triples accuracy while halving prompt length
- **Chunking benchmark** (Vecta, Feb 2026) — Recursive 512-token splitting at 69% accuracy; overlap provides no measurable benefit

### Benchmark Landscape

No existing benchmark tests documentation format impact on agent performance:

| Benchmark | Tests | Varies Doc Format? |
|-----------|-------|--------------------|
| SWE-bench | Agent coding ability | No |
| GAIA | Multi-step reasoning + tools | No |
| Tau-bench | Customer support + database state | No |
| WebArena | Web navigation | No |
| AgentBench | Multi-environment agent tasks | No |
| ToolLLM / BFCL | Tool/function calling accuracy | No |
| **This framework** | **Doc format impact on all of the above** | **Yes** |

### Industry Context

- **MCP adoption:** 97M+ monthly SDK downloads, 8M+ server downloads, 5,800+ servers, donated to Linux Foundation's Agentic AI Foundation (Dec 2025)
- **AGENTS.md adoption:** 60,000+ open source projects, backed by Linux Foundation
- **llms.txt adoption:** 844,000+ websites, but no confirmed LLM crawler consumption
- **Context engineering** has replaced prompt engineering as the dominant paradigm (Anthropic, LangChain, Manus AI, Martin Fowler all converging on this term)

---

## Phasing Summary

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| **A** | Real data + semantic scoring | First real findings from 9 datasets with judge validation |
| **B** | Operational metrics | Cost-efficiency Pareto frontiers, stability analysis |
| **C** | Modern agent patterns | MCP, compression, tool descriptions, AGENTS.md, hallucination |

Each phase builds on the previous. Phase A produces the first real findings. Phase B makes those findings production-relevant. Phase C extends them to how agents actually work today.
