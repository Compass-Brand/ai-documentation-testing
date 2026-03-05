# Plan: Context Strategy Modes for AI Documentation Testing

## Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 5   | 2026-03-05 | Lean review: dead code removal (~2,290 lines), extract shared registry utility, extend ResponseCache for embeddings, nested YAML for strategy sub-params (reduce CLI bloat), extract test factories to conftest, config bloat reduction (3 CLI flags instead of 8) |
| 4   | 2026-03-05 | Full-codebase review (153 files): fixed axis table errors, CLI full-mode orchestrator bypass, OracleBaseline lifecycle, error paths, cache invalidation, StrategyConfig composition, resume logic, ToolCallMetric confound, MetricContext gap, store/tracker/routes/history changes, token_counter reuse, RunManager wiring, cost.py limitation, doc_tree.files fix |
| 3   | 2026-03-04 | Complete integration point map, level mapping prerequisite, statistical methods |
| 2   | 2026-03-04 | Strategy as blocking variable, per-strategy repetitions, confound documentation |
| 1   | 2026-03-04 | Initial draft |

## Context

The framework currently only evaluates documentation formats via **full context injection** — stuffing the entire rendered index into the LLM prompt. This doesn't match how documentation is actually used in production (RAG retrieval, small system prompts, tool-based access). Results from the current approach may not transfer to real-world scenarios.

This change introduces a **ContextStrategy** abstraction that decouples documentation FORMAT (what variants control) from ACCESS PATTERN (how docs reach the LLM). Strategy is treated as a **blocking variable** — separate Taguchi screenings run per strategy, then results are compared in a cross-strategy meta-analysis. This answers: "Which doc format works best for each access pattern?"

### Why NOT a Taguchi Factor?

1. **Interaction is the research question.** We want format × strategy interactions. Taguchi assumes interactions are negligible — confounding them with main effects.
2. **S/N ratios are incomparable across modes.** Full context scores ~0.7-0.95, RAG ~0.5-0.8, tool-based ~0.3-0.9. Pooling makes strategy dominate, drowning format effects.
3. **Variance structures differ.** Full context: low variance. Tool-based: high variance. Equal reps give unequal statistical power.
4. **Pre-existing OA level mapping bug.** `factors.py:120-123` uses `mod N` breaking balance for mixed-level designs.

**Solution:** Treat strategy as a blocking variable. Run independent Taguchi screenings per strategy. Compare optimal configs across strategies in post-hoc meta-analysis.

## Prerequisites (Must Complete First)

### P0: Fix Level Mapping Bug (HARD BLOCKER)

`factors.py:120-123` uses `raw_level % factor.n_levels` to map OA column values to factor levels. This breaks balance whenever `column_levels != factor.n_levels`.

**Impact on current experiments (NOT just this plan):**

| Axis | Label | Variants | L50 Col Levels | Bug? |
|------|-------|----------|---------------|------|
| 1 | structure | 5 | 5 | No (exact match) |
| 2 | metadata | 4 | 5 | **YES**: `{0,1,2,3,4} % 4 = {0,1,2,3,0}` → level 0 gets 2x weight |
| 3 | format | 5 | 5 | No (exact match) |
| 4 | position | 4 | 5 | **YES** |
| 5 | transform | 5 | 5 | No (exact match) |
| 6 | scale | 5 | 5 | No (exact match) |
| 7 | noise | 4 | 5 | **YES** |
| 8 | granularity | 4 | 5 | **YES** |
| 9 | xref | 3 | 5 | **YES**: `{0,1,2,3,4} % 3 = {0,1,2,0,1}` → levels 0,1 get 2x weight |
| 10 | temporal | 4 | 5 | **YES** |

6 of 10 axes have broken balance. 4 axes (1, 3, 5, 6) have exact 5-level matches and work correctly. Any Taguchi experiment using the affected axes produces biased ANOVA results.

**Fix:** Use dummy-level exclusion (standard Taguchi approach). Add dummy variant levels to pad each factor to match the OA column level count. Exclude dummy-level rows from S/N ratio computation and ANOVA. This preserves balance without eliminating mixed-level OAs.

### P1: Fix Prediction Interval Bug (Pre-existing)

`analysis.py:388-399` computes prediction SE using total variance instead of ANOVA residual error:

```python
residual_var = sum((y - sn_mean) ** 2 for y in sn_values) / (n - 1)
se = math.sqrt(residual_var / n)
```

Should use `ms_error` from ANOVA with proper degrees of freedom. Current implementation produces methodologically incorrect prediction intervals (wrong df, includes factor-effect variance). The direction of bias depends on factor effect sizes vs error.

### P2: Fix LLMClient content=None Bug

`llm/client.py:124-143` treats `content=None` as a silent rate limit and retries. Tool call responses legitimately have `content=None` with `tool_calls` populated. Must check for `tool_calls` before assuming rate limit. This blocks Phase 4 but can be fixed independently.

## Architecture

### Core Abstraction: ContextStrategy

Sits between variant rendering and LLM execution:

```
CURRENT:  variant.render() → task.build_prompt(full_index) → client.complete() → score
NEW:      variant.render() → strategy.prepare(index, task) → strategy.execute(client) → score
```

#### Strategy Lifecycle (Per-Variant, NOT Per-Run)

**Critical:** `rendered_index` changes per variant (EvalRunner) or per OA row (TaguchiRunner). Strategy instances MUST be per-variant/per-row, not shared across the run.

- **EvalRunner:** Create a strategy instance per variant in the variant setup loop. Strategy.setup() is called once per variant with that variant's `render(doc_tree)` output.
- **TaguchiRunner:** Create a strategy instance per OA row in the pre-build loop (lines 114-118, alongside `row_composites`). Rendering moves from `_run_trial()` to the pre-build loop — each row's `composite.render(doc_tree)` is called once and stored. `_run_trial()` receives the pre-rendered index instead of re-rendering.
- **Thread safety:** Per-instance design eliminates shared-state issues. Each ThreadPoolExecutor work item has its own strategy instance.

**OracleBaseline / LengthMatchedRandomBaseline exception:** These baselines produce different `render()` output per task (via `_setup_variant_for_task()` in runner.py:619-650). For non-full strategies, this means the strategy would need re-setup per task (expensive for RAG embedding). **Resolution:** Exclude axis-0 baselines from non-full strategies. Baselines measure upper/lower bounds and only make sense with full_context. Document this as a known limitation. If baseline support is needed later, add a `needs_per_task_setup` flag to the variant interface.

#### Module Structure

```
agent_evals/context/
    __init__.py
    base.py              # ContextStrategy ABC, PreparedContext, StrategyResult
    registry.py          # Auto-discovery (mirrors variants/registry.py pattern)
    full.py              # FullContextStrategy (current behavior, default)
    system_prompt.py     # SystemPromptStrategy (token-budget constrained)
    rag.py               # RAGStrategy (chunk → embed → retrieve → inject)
    tool_based.py        # ToolBasedStrategy (multi-turn with doc tools)
    chunkers.py          # Fixed, heading-based chunking
    embedder.py          # Thin wrapper around litellm.embedding()
    vector_store.py      # In-memory cosine similarity search (numpy)
```

### Key Interfaces

```python
class ContextStrategy(ABC):
    """Base class for all context delivery strategies."""

    @abstractmethod
    def name(self) -> str: ...

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        """One-time setup per variant/OA-row. Called before any trials."""
        pass

    def teardown(self) -> None:
        """Cleanup after all trials for this variant/row."""
        pass

    @abstractmethod
    def prepare(self, rendered_index: str, task: EvalTask, doc_tree: DocTree) -> PreparedContext:
        """Prepare context for a single trial. Must be thread-safe."""
        ...

    @abstractmethod
    def execute(
        self, prepared: PreparedContext, task: EvalTask,
        client: LLMClient, max_tokens: int, temperature: float,
    ) -> StrategyResult:
        """Execute the LLM interaction. Single-turn or multi-turn."""
        ...

    def supports_caching(self) -> bool:
        """Whether results from this strategy are deterministic and cacheable."""
        return True


@dataclass
class PreparedContext:
    """Output of prepare() — input to execute()."""
    messages: list[dict]           # For single-turn strategies
    tools: list[dict] | None       # For tool-based strategy
    strategy_metadata: dict[str, Any]  # Chunks retrieved, tokens after truncation, etc.


@dataclass
class StrategyResult:
    final_response: str
    generations: list[GenerationResult]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float | None
    messages: list[dict]           # Full message history (for tool-based: all turns)
    strategy_metadata: dict[str, Any]


@dataclass
class StrategyConfig:
    """Configuration for context strategy construction."""
    strategy: str = "full_context"
    token_budget: int | None = None
    truncation: str = "hard"
    chunk_method: str = "heading"
    rag_top_k: int = 5
    embedding_model: str = "text-embedding-3-small"
    max_turns: int = 10
```

### How Each Mode Works

**Full Context (current, default):**
- `prepare()`: calls `task.build_prompt(rendered_index)` → returns messages in PreparedContext
- `execute()`: calls `client.complete(messages)` → wraps in StrategyResult
- `supports_caching()`: True
- Identical to current behavior.

**System Prompt:**
- `prepare()`: truncates rendered_index to token budget using `llm/token_counter.py:count_tokens()` (reuse existing utility), then calls `task.build_prompt(truncated)` → returns messages
- Truncation methods:
  - **Hard cutoff**: simple token-count truncation
  - **Priority-based**: accesses `doc_tree.files` (dict of DocFile objects) to identify tier metadata (required/recommended/optional via `DocFile.tier` and `DocFile.priority`), uses `tiers.sort_files_bluf()` for priority ordering, keeps required-tier content first, then fills remaining budget
- `execute()`: single-turn like full context
- `supports_caching()`: True
- Tests: which FORMAT packs the most useful info per token?

**RAG:**
- `setup()`: chunks the rendered_index and embeds all chunks (one-time per variant/row)
- `prepare()`: embeds the task question, retrieves top-K similar chunks, builds messages with only retrieved chunks
- `execute()`: single-turn LLM call with retrieved context
- `supports_caching()`: True (same question + same chunks = same retrieval)
- Tests: which FORMAT survives chunking best?

**Tool-Based:**
- `setup()`: stores rendered_index and doc_tree for tool responses
- `prepare()`: builds tool definitions + initial user message (task question only, NO index in prompt)
- `execute()`: multi-turn agentic loop — LLM calls tools, gets results, continues until final answer or MAX_TURNS. `StrategyResult.final_response` is cleaned of tool-call artifacts before scoring.
- Tools: `list_docs` (returns variant-rendered index), `read_doc` (returns raw content from DocTree by path), `search_docs` (substring search)
- `supports_caching()`: False (non-deterministic multi-turn)
- Tests: does index format help the agent navigate and find the right files?

### Caching Architecture

Cache stays at the `_run_trial()` level in EvalRunner, NOT inside strategies:

```python
# In runner.py _run_trial():
if strategy.supports_caching():
    cache_key = build_cache_key(task, variant, strategy.name())
    cached = cache.get(cache_key)
    if cached:
        return cached_to_trial_result(cached)

result = strategy.execute(prepared, task, client, ...)

if strategy.supports_caching():
    cache.set(cache_key, result)
```

**Cache invalidation:** For `full_context` strategy, do NOT include strategy name in cache key — this preserves existing caches and maintains backward compat. For all other strategies, include strategy name.

TaguchiRunner has NO caching. This plan does NOT add caching to TaguchiRunner — it remains uncached regardless of strategy.

### Complete Integration Point Map

Every file that needs modification, organized by phase:

#### Runner Chain (Phase 1)

| File | What Changes | Details |
|------|-------------|---------|
| `runner.py` | `EvalRunner.__init__()` | Accept `strategy_factory: Callable[[], ContextStrategy]` parameter. Default: `lambda: FullContextStrategy()` |
| `runner.py` | `EvalRunner._setup_variants()` | After `variant.setup(doc_tree)`, create per-variant strategy instance and call `strategy.setup(variant.render(doc_tree), doc_tree)`. Skip strategy setup for OracleBaseline/LengthMatchedRandomBaseline when strategy is not full_context. |
| `runner.py` | `EvalRunner._run_trial()` | Replace render → build_prompt → complete with `strategy.prepare() → strategy.execute()`. Update cache key (include strategy name only for non-full_context). Update error paths to include `context_strategy`, `strategy_metadata`, `llm_calls` in TrialResult. |
| `runner.py` | `EvalRunner._teardown_variants()` | Add `strategy.teardown()` per variant |
| `runner.py` | CSV/JSON report field lists (lines 540-554, 450-467) | Add `context_strategy`, `llm_calls`, `strategy_metadata` to both trial_dicts and CSV headers |
| `runner.py` | `TrialResult` dataclass | Add optional: `context_strategy: str | None = None`, `strategy_metadata: dict = field(default_factory=dict)`, `llm_calls: int = 1` |
| `runner.py` | Judge sampling (lines 798-811) | Change `generation.content` to `strategy_result.final_response`. Judge does NOT need strategy awareness — it scores the final answer regardless of how it was produced. |
| `taguchi/runner.py` | `TaguchiRunner.__init__()` | Accept `strategy_factory: Callable[[], ContextStrategy]` |
| `taguchi/runner.py` | `TaguchiRunner.run()` pre-build loop (lines 114-118) | Create per-row strategy instances alongside `row_composites`. Call `composite.render(doc_tree)` here and store the rendered index. |
| `taguchi/runner.py` | `TaguchiRunner._run_trial()` | Replace render → build_prompt → complete with strategy.prepare() → strategy.execute(). Use pre-rendered index instead of re-rendering. Update error path to include new TrialResult fields. |
| `taguchi/runner.py` | `TaguchiRunner.run()` finally block (lines 237-247) | Add per-row strategy.teardown() |

#### LLM Client (Phase 4 — Tool-Based Only)

| File | What Changes | Details |
|------|-------------|---------|
| `llm/client.py` | `LLMClient.complete()` | Add explicit `tools: list[dict] | None = None` parameter for type safety (already passes through via `**kwargs` but making it explicit). Extract `tool_calls` from response when present. |
| `llm/client.py` | `GenerationResult` | Add optional `tool_calls: list | None = None` field |
| `llm/client.py` | Content=None handling | **P2 fix:** Check for `tool_calls` before treating `content=None` as rate limit retry |

#### Orchestrator/Pipeline Chain (Phase 5)

| File | What Changes | Details |
|------|-------------|---------|
| `orchestrator.py` | `OrchestratorConfig` | Add `strategy_config: StrategyConfig = field(default_factory=StrategyConfig)` (single composed dataclass, not flat fields) |
| `orchestrator.py` | `EvalOrchestrator._run_taguchi()` | Pass `strategy_factory` to TaguchiRunner constructor |
| `orchestrator.py` | `EvalOrchestrator._run_full()` | Pass `strategy_factory` to EvalRunner constructor |
| `pipeline.py` | `PipelineConfig` | Add `strategy_config: StrategyConfig = field(default_factory=StrategyConfig)`, `strategy_reps: dict[str, int] = field(default_factory=dict)` |
| `pipeline.py` | New class `MultiStrategyPipeline` | Iterates over strategies, deep-copies PipelineConfig per strategy, overrides reps from strategy_reps, creates separate DOEPipeline per strategy with strategy-specific pipeline_id (e.g., `pipe-001__rag`). Includes per-strategy resume tracking (which strategies completed, which in-progress). |
| `cli.py` | `build_parser()` | Add only 3 CLI flags: `--context-strategy` (single strategy), `--strategies` (comma-separated for multi-strategy), `--strategy-reps` (e.g., `"tool_based=10,rag=5"`). All other strategy sub-parameters (`token_budget`, `truncation`, `chunk_method`, `rag_top_k`, `embedding_model`, `max_turns`) are **YAML-only** under a nested `strategy_config:` section. This keeps CLI at 53 flags (from 50), not 58. |
| `cli.py` | `_CONFIG_KEYS` (lines 409-447) | Add 3 new CLI config key mappings. Strategy sub-parameters resolved from YAML `strategy_config:` section only. |
| `cli.py` | `_main()` full-mode path (lines 771-781) | **CRITICAL FIX:** Currently bypasses orchestrator entirely for `mode == "full"`, creating EvalRunner directly. Must either route through orchestrator (which has `_run_full()`) or construct strategy_factory in CLI and pass to EvalRunner. Route through orchestrator for consistency. |
| `cli.py` | `_main()` | Route `--strategies` to MultiStrategyPipeline, single `--context-strategy` to DOEPipeline with strategy config |
| `observatory/run_manager.py` | `StartRunRequest` | Add strategy_config fields. Pass through to OrchestratorConfig. |

#### Observatory/Reports (Phase 6)

| File | What Changes | Details |
|------|-------------|---------|
| `observatory/store.py` | Schema migration (`_migrate_schema()`) | Add 3 ALTER TABLE statements for `context_strategy`, `llm_calls`, `strategy_metadata`. Add index on `context_strategy`. |
| `observatory/store.py` | `TrialRecord` dataclass | Add `context_strategy: str = "full_context"`, `llm_calls: int = 1`, `strategy_metadata: dict | None = None` |
| `observatory/store.py` | `record_trial()` | Accept and INSERT 3 new fields |
| `observatory/store.py` | `get_trials()` | Add optional `context_strategy` filter parameter. Deserialize `strategy_metadata` JSON on read. |
| `observatory/store.py` | `get_run_aggregates()` | Add `by_strategy` aggregation alongside existing `by_variant` and `by_model` |
| `observatory/tracker.py` | `EventTracker.record_trial()` | Accept 3 new params, pass through to store. Include `context_strategy` in `trial_completed` event data. |
| `observatory/history.py` | `compare_runs()`, `variant_performance_trend()`, `detect_regressions()`, `model_ranking()` | Add optional `context_strategy` filter parameter |
| `observatory/web/routes.py` | Existing endpoints | Add `?strategy=rag` query parameter filter on `list_runs`, `get_trials`. Add `by_strategy` to `_enrich_run`. |
| `observatory/web/routes.py` | New endpoint | `GET /api/runs/{run_id}/strategy-comparison` for cross-strategy meta-analysis results |
| `observatory/web/routes.py` | SSE streaming | Include `context_strategy` in `trial_completed` event data |
| `reports/aggregator.py` | `ReportData` | Add `context_strategy: str = "full_context"`, `strategy_comparison: dict | None = None` |
| `reports/statistics.py` | New functions | `kendalls_w(rankings)` — coefficient of concordance (pure Python, scipy doesn't have it directly). `friedman_test(data)` — wraps `scipy.stats.friedmanchisquare()`. |
| `reports/html_renderer.py` | New section | "Cross-Strategy Comparison" with significance matrix heatmap (Plotly) |
| `reports/md_renderer.py` | New function | `_render_strategy_comparison()` — concordance table |
| `reports/charts.py` | New functions | `generate_strategy_comparison_chart()`, `generate_concordance_chart()` |

#### Files That Do NOT Change (Verified by Full Codebase Review)

**Tasks (11 types):** All `build_prompt()` methods take `index_content: str` — truncated, RAG-retrieved, or empty all work transparently. All `score_response()` methods work purely on response text, no assumptions about index content. ✓

**Variants (47 variants):** All `render()` methods unchanged. `variants/registry.py` provides a reusable auto-discovery pattern for `context/registry.py`. ✓

**Taguchi analysis:** `taguchi/analysis.py` — S/N ratios, ANOVA, main effects unchanged (run separately per strategy). `taguchi/catalog.py` — OA catalog unchanged. `taguchi/factors.py` — strategy is NOT a factor (except P0 level mapping fix). ✓

**Other unchanged modules:**
- `diagnostics.py` — per-strategy isolation happens naturally (each DOEPipeline creates its own tracker). Correctly tracks `total_tokens` from StrategyResult. ✓
- `scoring.py` — task scoring unchanged ✓
- `source.py` — source tracking unchanged ✓
- `datasets/` — all dataset loaders unchanged (produce DocTree/tasks, no context dependency) ✓
- `judge/` — judge poll and calibrator work on (question, response) pairs, strategy-agnostic ✓
- `agent-index/` — entire agent-index package unchanged ✓
- `llm/cache.py` — cache logic stays at runner level (extended for EmbeddingCache, see Code Reuse) ✓
- `llm/client_pool.py` — manages per-model clients, strategy-agnostic ✓
- `llm/token_counter.py` — pure utility, reused by system_prompt strategy ✓
- `cost.py` — **Note:** dry-run cost estimates will be inaccurate for non-full strategies (overestimates for system_prompt/RAG since it uses full prompt size, indeterminate for tool-based). Document as known limitation. ✓

**Dead code — candidates for removal (separate PR, not part of this plan):**

| File | Lines | Tests | Evidence |
|------|-------|-------|----------|
| `beam_search.py` | 325 | 309 (21 methods) | Zero imports from any production module |
| `factorial.py` | 237 | 321 (23 methods) | Zero imports from production; only referenced in docstrings |
| `interaction_analysis.py` | ~200 | unknown | Zero imports from anywhere in `src/` |
| `pilot/` (3 files) | ~900 | none | Zero imports; standalone experiment scripts |

**Total: ~2,290 lines.** These inflate the codebase and coverage metrics without contributing. Removal should be a separate cleanup PR before or after this plan, NOT interleaved with context strategy implementation.

#### Metrics Module — Known Confound

`metrics/tool_calls.py` (`ToolCallMetric`) scores `1.0 - min(actual_calls / max_expected, 1.0)` where `max_expected=10`. In tool-based strategy mode, the LLM is expected to make multiple tool calls, so this metric penalizes correct behavior. **Resolution:** ToolCallMetric is not used in Taguchi S/N ratios (metrics are supplementary, not part of `score_response()`). Document the confound. If ToolCallMetric is used directly, disable it for tool_based strategy runs.

`metrics/base.py:MetricContext.tool_calls` is currently populated from the task's tool calls. For tool-based strategy, tool calls come from `StrategyResult.messages`. The runner needs to extract tool calls from the strategy result message history and populate `MetricContext` accordingly when metrics are computed.

### Code Reuse

| Existing Code | Reused For | How |
|--------------|------------|-----|
| `variants/registry.py` auto-discovery pattern | `context/registry.py` | **Extract** shared `auto_discover_modules(package)` utility that both registries call, instead of copy-pasting the 30-line pkgutil pattern |
| `llm/token_counter.py:count_tokens()` | System prompt truncation | Import and call directly — wraps litellm with `len(text) // 4` fallback. Do NOT call `litellm.token_counter()` directly |
| `llm/cache.py:ResponseCache` | RAG embedding cache | **Extend or adapt** — ResponseCache already has SHA-256 hashing (`make_key()`), atomic writes via `tempfile.mkstemp() + os.replace()`, TTL expiry, LRU eviction, thread-safe `threading.Lock`. Create `EmbeddingCache` that inherits/adapts this rather than reimplementing |
| `agent_index/tiers.py:sort_files_bluf()` | Priority-based truncation ordering | Import and call directly |
| `reports/statistics.py` | Kendall's W + Friedman | **Add to existing module** — don't create new file. Module already has `benjamini_hochberg()`, `compute_effect_sizes()`, `tukey_hsd()`, `omega_squared()` |
| `scoring.py:pairwise_wilcoxon()` | Potentially reusable for strategy-specific optimal comparison | Import if needed |
| `tasks/_utils.py:extract_keywords()` | Tool-based `search_docs` keyword extraction | Minor reuse opportunity — used by 8 task types already |

### No New Dependencies
- Embeddings: `litellm.embedding()` (available in litellm 1.81.8, currently installed)
- Vector math: `numpy` 2.4.2 (already installed)
- Token counting: `llm/token_counter.py` (existing utility wrapping litellm/tiktoken)
- Tool calling: `litellm.completion(tools=...)` (already supported)
- Friedman's test: `scipy.stats.friedmanchisquare()` (scipy already installed)
- Chunking: pure Python with regex
- Kendall's W: pure Python implementation (no external library needed)

**OpenRouter embedding caveat:** OpenRouter supports 49 embedding models via litellm, but litellm's `model_cost` dict lacks OpenRouter embedding cost data. Cost tracking for RAG setup may show `cost=None`. Recommend using direct OpenAI endpoint for embeddings (separate API key) for proper cost tracking, or accept `cost=None`.

## Experimental Design

### Strategy as Blocking Variable

Each strategy gets its own independent Taguchi analysis:

```
Pipeline with --strategies "full_context,rag,system_prompt,tool_based":

  Strategy: full_context
    └── Screening (L50, 3 reps) → significant factors → Confirmation → Refinement
    └── Result: optimal_full = {structure: nested, format: markdown, ...}

  Strategy: rag (chunk=heading, rag_top_k=5, embed=text-embedding-3-small)
    └── Screening (L50, 5 reps) → significant factors → Confirmation → Refinement
    └── Result: optimal_rag = {structure: flat, format: yaml, ...}

  Strategy: system_prompt (budget=4096, truncation=priority)
    └── Screening (L50, 3 reps) → significant factors → Confirmation → Refinement
    └── Result: optimal_sysprompt = {structure: nested, format: compact, ...}

  Strategy: tool_based (max_turns=10)
    └── Screening (L50, 10 reps) → significant factors → Confirmation → Refinement
    └── Result: optimal_tool = {structure: nested, format: markdown, ...}

  Cross-Strategy Meta-Analysis:
    └── Compare factor rankings using Kendall's W (coefficient of concordance)
    └── Per-factor Friedman test: does optimal level differ across strategies?
    └── Significance matrix showing robust vs strategy-dependent factors
    └── Recommendation matrix: optimal level per factor per strategy
```

### Per-Strategy Repetition Counts

| Strategy | Default Screening Reps | Default Confirmation Reps | Rationale |
|----------|----------------------|--------------------------|-----------|
| full_context | 3 | 5 | Low variance, deterministic single-turn |
| system_prompt | 3 | 5 | Low-medium variance, deterministic |
| rag | 5 | 7 | Medium variance, chunking adds noise |
| tool_based | 5 (start conservative) | 7 | High variance; increase to 10 if MS_error too large to reach significance |

Rule: `confirmation_reps = screening_reps + 2` per strategy (minimum 5).

CLI: `--screening-reps` sets the base. Per-strategy overrides via `--strategy-reps "tool_based=10,rag=5"`.

### Confound Documentation

| Strategy | Fixed Parameters | What They Confound |
|----------|------------------|--------------------|
| RAG | embedding_model, chunk_method, rag_top_k | Retrieval quality × format quality |
| System Prompt | token_budget, truncation_method | Compression quality × format density |
| Tool-Based | max_turns, tool_definitions, temperature | Agent strategy × format navigability |

Results should be reported as conditional: "YAML is optimal for RAG **with heading-based chunking, top-5 retrieval, text-embedding-3-small**."

### Cross-Strategy Meta-Analysis

**Statistical methods:**
- **Do NOT pool S/N ratios across strategies** — scales are incomparable
- **Compare factor RANKINGS, not magnitudes** — for each strategy, rank levels within each factor by mean S/N
- **Kendall's W (coefficient of concordance)** — tests whether strategies agree on level ordering. Implementation: pure Python (`W = 12 * S / (m^2 * (k^3 - k))`)
- **Friedman's test (per factor)** — tests whether optimal level differs across strategies. Implementation: `scipy.stats.friedmanchisquare()` with strategies as blocks, factor levels as treatments
- **No family-wise correction across strategies** — each screening answers an independent research question. BH correction within each screening (already implemented) is sufficient
- **Interleaved scheduling recommended** — run row 1 for all strategies, then row 2, etc., to distribute temporal effects evenly

**Reporting format:**

```
Factor        | full   | system | rag    | tool   | Concordance
axis_3_format | md **  | md **  | yaml **| md **  | W=0.82 (robust)
axis_7_noise  | none   | low *  | high **| low    | W=0.31 (strategy-dependent)
axis_9_xref   | none   | light *| dense**| dense *| W=0.55 (moderate)
```

Report ALL factors across ALL strategies. Factors significant in only 1 strategy are the most interesting findings — they reveal strategy-format interactions.

## Implementation Phases

### Phase 1: Foundation + Full Context Strategy
Create the abstraction layer and verify it reproduces current behavior exactly.

1. Create `context/base.py` — ABC, PreparedContext, StrategyResult, StrategyConfig dataclasses
2. Create `context/full.py` — FullContextStrategy (wraps current behavior)
3. Create `context/registry.py` — auto-discovery registry (mirror `variants/registry.py` pattern)
4. Modify `runner.py`:
   - Accept `strategy_factory` in `EvalRunner.__init__()`
   - Per-variant strategy instances in `_setup_variants()` / `_teardown_variants()`
   - Replace render → build_prompt → complete with prepare → execute in `_run_trial()`
   - Skip strategy setup for OracleBaseline/LengthMatchedRandomBaseline when strategy is not full_context
   - Update error paths to include new TrialResult fields
   - Update cache key (only for non-full_context strategies)
   - Update CSV/JSON report field lists
   - Update judge sampling to use `strategy_result.final_response`
5. Modify `taguchi/runner.py`:
   - Accept `strategy_factory` in `TaguchiRunner.__init__()`
   - Per-row strategy instances in pre-build loop (move `composite.render()` here)
   - Replace render → build_prompt → complete with prepare → execute in `_run_trial()`
   - Update error path with new TrialResult fields
   - Add strategy.teardown() in finally block
6. Extend `TrialResult` — `context_strategy`, `strategy_metadata`, `llm_calls` fields
7. Tests: verify ALL existing tests pass unchanged with FullContextStrategy default

### Phase 2: System Prompt Mode

1. Create `context/system_prompt.py` — truncation at configurable token budgets
2. Two truncation methods:
   - **Hard cutoff**: token-count truncation using `llm/token_counter.py:count_tokens()` (reuse existing utility)
   - **Priority-based**: accesses `doc_tree.files` (dict of DocFile objects) to get tier metadata, uses `tiers.sort_files_bluf()` for priority ordering, keeps required-tier content first, then fills remaining budget
3. CLI: `--context-strategy system_prompt`. Sub-parameters `token_budget` and `truncation` configured via YAML `strategy_config:` section.
4. Tests: truncation correctness, budget enforcement, priority ordering, strategy metadata

### Phase 3: RAG Mode

1. Create `context/chunkers.py` — fixed-size (token count via `count_tokens()`) and heading-based (split on `#`/`##` markers) chunkers
2. Create `context/embedder.py` — `litellm.embedding()` wrapper with content-hash caching (SHA256 → embedding vector, persisted to disk). Reuse hashing pattern from `llm/cache.py:ResponseCache.make_key()`.
3. Create `context/vector_store.py` — InMemoryVectorStore: numpy cosine similarity, read-only after construction (thread-safe). Benchmarked: 2350×1536 matrix = 15ms.
4. Create `context/rag.py` — RAGStrategy. setup() chunks + embeds rendered index. prepare() embeds task question + retrieves top-K chunks. execute() builds prompt with retrieved chunks and calls client.complete().
5. CLI: `--context-strategy rag`. Sub-parameters `chunk_method`, `rag_top_k`, `embedding_model` configured via YAML `strategy_config:` section.
6. Tests: chunking strategies, embedding mock, retrieval accuracy, end-to-end RAG flow

### Phase 4: Tool-Based Mode

1. Extend `llm/client.py`:
   - Add explicit `tools` parameter to `complete()` for type safety
   - Add `tool_calls` field to `GenerationResult`
   - **P2 fix:** `content=None` handling — check for `tool_calls` before assuming rate limit
2. Create `context/tool_based.py` — ToolBasedStrategy:
   - setup(): stores rendered_index and doc_tree
   - prepare(): builds tool definitions + initial user message (task question, no index in prompt)
   - execute(): multi-turn loop with MAX_TURNS cap (default 10):
     - Call client.complete(messages, tools=tool_defs)
     - If response has tool_calls: execute tools, append results, loop
     - If response has text content (no tool_calls): return as final answer
     - If MAX_TURNS reached: return last response
     - `final_response` is cleaned of tool-call artifacts before returning
   - Tools:
     - `list_docs()` → returns variant-rendered index (format matters for navigation)
     - `read_doc(path: str)` → returns raw file content from DocTree by path
     - `search_docs(query: str)` → substring search across DocTree content, returns matching snippets
3. `supports_caching()` returns False (non-deterministic multi-turn)
4. `StrategyResult.messages` contains the full multi-turn history — **storage note:** for tool-based, `prompt_messages` on TrialResult should contain only the initial messages (not the full conversation) to avoid bloating observatory storage. The full conversation is available via `strategy_metadata` if `store_traces` is enabled.
5. MetricContext.tool_calls population: the runner extracts tool calls from `StrategyResult.messages` to populate `MetricContext` when computing metrics.
6. Tests: tool dispatch, multi-turn loop, max turns enforcement, tool error handling, content=None with tool_calls

### Phase 5: Multi-Strategy Pipeline + CLI

1. Extend `pipeline.py`:
   - Add `strategy_config: StrategyConfig` to `PipelineConfig`
   - Add `strategy_reps: dict[str, int]` to PipelineConfig
   - New `MultiStrategyPipeline` class:
     - Takes list of strategy names + per-strategy config overrides
     - Deep-copies PipelineConfig per strategy (avoids shared-state mutation)
     - Overrides `screening_reps` and `confirmation_reps` from `strategy_reps` mapping
     - Runs independent DOEPipeline per strategy with strategy-specific pipeline_id (e.g., `pipe-001__rag`)
     - Returns `MultiStrategyResult` with per-strategy results + meta-analysis
     - **Resume support:** Tracks per-strategy completion status. `--resume-pipeline` checks which strategy sub-pipelines completed and resumes from the first incomplete one.
2. Extend orchestrator chain:
   - Add `strategy_config: StrategyConfig` to `OrchestratorConfig`
   - `EvalOrchestrator._run_taguchi()` and `_run_full()` pass `strategy_factory` to runners
   - Strategy factory constructed from `strategy_config`
3. CLI:
   - `--strategies "full_context,rag,system_prompt"` → MultiStrategyPipeline
   - `--strategy-reps "tool_based=10,rag=5"` → per-strategy rep overrides
   - Single `--context-strategy rag` → single DOEPipeline with that strategy
   - **CRITICAL FIX:** Full-mode path (lines 771-781) must route through orchestrator instead of creating EvalRunner directly, so strategy gets wired.
4. `observatory/run_manager.py` — add strategy fields to `StartRunRequest`, pass through to `OrchestratorConfig`
5. Tests: multi-strategy pipeline flow, per-strategy rep overrides, deep-copy isolation, resume logic, meta-analysis output

### Phase 6: Observatory + Reports

1. Observatory schema — add columns with defaults for backward compat:
   - `context_strategy TEXT DEFAULT 'full_context'`
   - `llm_calls INTEGER DEFAULT 1`
   - `strategy_metadata TEXT` (JSON blob)
   - `CREATE INDEX IF NOT EXISTS idx_trials_strategy ON trials (context_strategy)`
2. `TrialRecord` — add fields + `json.loads()` deserialization for `strategy_metadata` in `get_trials()`
3. `store.record_trial()` — accept and INSERT 3 new fields
4. `store.get_trials()` — add optional `context_strategy` filter parameter
5. `store.get_run_aggregates()` — add `by_strategy` grouping (GROUP BY variant_name, context_strategy)
6. `EventTracker.record_trial()` — accept 3 new params, pass through, include `context_strategy` in `trial_completed` event
7. `history.py` — add optional `context_strategy` filter to `compare_runs()`, `variant_performance_trend()`, `detect_regressions()`, `model_ranking()`
8. `reports/statistics.py` — implement `kendalls_w()` (pure Python) and `friedman_test()` (wraps scipy)
9. Report aggregator — add `context_strategy` and `strategy_comparison` to `ReportData`
10. Cross-strategy report:
    - Significance matrix (factor × strategy, showing p-values and optimal levels)
    - Kendall's W concordance scores per factor
    - Friedman test p-values for strategy-dependent factors
    - Recommendation matrix with robustness annotations
11. `reports/html_renderer.py` — new "Cross-Strategy Comparison" section with heatmap chart
12. `reports/md_renderer.py` — new `_render_strategy_comparison()` function
13. `reports/charts.py` — new `generate_strategy_comparison_chart()`, `generate_concordance_chart()`
14. `observatory/web/routes.py` — strategy query filters, `by_strategy` enrichment, SSE event data, new comparison endpoint
15. `observatory/cli.py` — optional strategy filter display (low priority)
16. `observatory/terminal.py` — optional strategy column (low priority)
17. Tests: schema migration, aggregation with strategy grouping, JSON deserialization, meta-analysis computations, Kendall's W correctness, Friedman's test correctness

### YAML Strategy Configuration

Strategy sub-parameters live in a nested `strategy_config:` section in the YAML config file, NOT as CLI flags:

```yaml
# Single strategy
context_strategy: rag
strategy_config:
  chunk_method: heading
  rag_top_k: 5
  embedding_model: text-embedding-3-small
  token_budget: 4096
  truncation: priority
  max_turns: 10

# Multi-strategy comparison
strategies:
  - full_context
  - rag
  - system_prompt
strategy_reps:
  tool_based: 10
  rag: 5
strategy_config:
  chunk_method: heading
  rag_top_k: 5
  embedding_model: text-embedding-3-small
  token_budget: 4096
```

The existing `resolve_config()` function already handles YAML → dict merging. Adding a nested `strategy_config` section is a natural extension.

### Test Infrastructure Prerequisites

Before writing context strategy tests, **extract shared test factories** to avoid further duplication:

**Current duplication across test files:**

| Factory | `test_runner.py` | `test_taguchi_runner.py` | `test_orchestrator.py` |
|---------|-----------------|--------------------------|------------------------|
| `_make_mock_task()` | full | simplified | via `_make_trial()` |
| `_make_mock_client()` | full | simplified | — |
| `_make_mock_variant()` | full | simplified | — |

**Action:** Extract to `tests/conftest.py` (currently minimal — just path setup):
- `make_mock_task()` — shared mock task factory
- `make_mock_client()` — shared mock LLM client factory
- `make_mock_variant()` — shared mock variant factory
- `make_mock_strategy()` — new, mock ContextStrategy with configurable `prepare()`/`execute()`
- `make_prepared_context()` — new, PreparedContext with messages and metadata
- `make_strategy_result()` — new, StrategyResult wrapping GenerationResult

This is a Phase 1 prerequisite — do it before writing context strategy tests.

## Verification

After each phase:
1. `uv run pytest` — all existing tests pass (backward compat)
2. `uv run pytest agent-evals/tests/test_context*.py` — new tests pass
3. Phase 1: `uv run agent-evals --dry-run` works identically to before
4. Phase 2: `uv run agent-evals --context-strategy system_prompt --config strategy_config.yaml --dry-run`
5. Phase 3: `uv run agent-evals --context-strategy rag --config strategy_config.yaml --dry-run`
6. Phase 4: `uv run agent-evals --context-strategy tool_based --config strategy_config.yaml --dry-run`
7. Phase 5: `uv run agent-evals --mode taguchi --strategies "full_context,rag,system_prompt" --dry-run`

## Known Limitations

| Limitation | Reason | Workaround |
|------------|--------|------------|
| OracleBaseline/LengthMatchedRandomBaseline only work with full_context strategy | These baselines produce per-task renders; non-full strategies cache rendered index at setup time | Axis-0 baselines are excluded from non-full strategy runs. Add `needs_per_task_setup` flag later if needed. |
| cost.py dry-run overestimates for non-full strategies | Dry-run renders full prompt; system_prompt/RAG use less | Accept inaccuracy or add strategy-aware estimation later |
| ToolCallMetric penalizes tool-based strategy | Metric penalizes >10 tool calls; tool-based strategy relies on tool calls | Disable ToolCallMetric for tool_based runs, or document as confound |
| OpenRouter embedding cost tracking shows cost=None | litellm `model_cost` lacks OpenRouter embedding pricing | Use direct OpenAI endpoint for embeddings |
| progress.py shows gaps during tool-based trials | Single trial = multiple LLM calls; progress fires per trial not per call | Document UX gap; add optional per-call progress callback later |
| Friedman's test has limited power with 4 strategies | n=4 blocks with k=3-5 treatments; asymptotic chi-square marginally accurate | Meta-analysis is exploratory, not confirmatory. Document this. |
| Dummy-level exclusion slightly breaks inter-factor orthogonality | Excluding dummy rows for a factor means remaining rows aren't perfectly balanced across other factors | Acceptable for screening. For axis 9 (3 levels, 20 dummy rows excluded), 30 rows remain with approximate balance. |
| Kendall's W tie handling | Standard formula assumes no tied ranks; exact S/N ties are unlikely but possible | Implement tie-corrected version or break ties arbitrarily |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Tool-based cost (5-10 reps × 50 rows × ~5 turns = 1,250-2,500 LLM calls per screening) | High | MAX_TURNS cap, budget guardrails. Start at 5 reps, increase if MS_error too large. |
| RAG embedding cost (47 variants × N chunks × embedding calls) | Medium | Content-hash caching. Use direct OpenAI for cost tracking. |
| Multi-strategy wall-clock time (4 separate pipelines = 4x time) | Medium | Strategy runs can be parallelized or resumed independently. Interleaved scheduling. |
| Thread safety | Low | Per-instance strategy design. InMemoryVectorStore read-only after setup. |
| Caching asymmetry (EvalRunner has cache, TaguchiRunner doesn't) | Low | Documented. TaguchiRunner intentionally uncached. |
| Confound sensitivity | Medium | Results conditional on fixed sub-parameters. Documented prominently. |
| Cache invalidation on upgrade | Low | full_context preserves existing cache keys. Other strategies get new keys. |

## Design Decisions

### D1: prepare() builds messages, execute() calls client

For single-turn: `prepare()` calls `task.build_prompt(modified_index)` → messages in PreparedContext. `execute()` calls `client.complete(messages)`.

For tool-based: `prepare()` builds tool definitions + initial user message (bypasses `task.build_prompt()`). `execute()` manages multi-turn loop.

The ABC is a loose contract — `execute()` means "produce a StrategyResult from a PreparedContext" regardless of turn count.

### D2: Embed the rendered index, not raw content

RAG chunks and embeds the variant-rendered index. Format affects retrieval quality. Tests the full hypothesis: "does format affect retrieval AND comprehension?"

### D3: list_docs returns variant-rendered index

Tool-based `list_docs` returns the variant-rendered index. Format directly affects agent navigation.

### D4: Report all factors, annotate with robustness

Cross-strategy results report ALL factors. Factors significant in only 1 strategy are the most interesting.

### D5: Cache at _run_trial level, not inside strategies

Cache logic in `_run_trial()` checks `strategy.supports_caching()`. Avoids duplicating cache logic across 4 strategies.

### D6: Strategy factory pattern

Runners accept `strategy_factory: Callable[[], ContextStrategy]`. Factory creates per-variant/per-row instances. Factory encapsulates StrategyConfig.

### D7: StrategyConfig composition over flat fields

Strategy parameters are composed into a `StrategyConfig` dataclass embedded in `PipelineConfig` and `OrchestratorConfig`. Avoids config field proliferation. New strategies add fields to StrategyConfig, not to every config class in the chain.
