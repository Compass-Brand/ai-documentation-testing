# Agent Knowledge Organizer — Epic & Story Breakdown

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build two Python packages (`agent-index` + `agent-evals`) that determine optimal documentation index formats for AI coding agents.

**Architecture:** UV workspace with shared types. Eval framework tests 10 axes × ~3-4 variants each via beam search. Results drive organizer's output format.

**Tech Stack:** Python, Pydantic v2, LiteLLM, OpenRouter, RAGAS (faithfulness metric)

---

## Dependency Graph (High Level)

```
Phase 1 ──────────────┬──────────────> Phase 8 ──> Phase 9
(agent-index core)    │                   ▲         Phase 10
                      │                   │
Phase 2 ──────────────┘                   │
(agent-evals core)                        │
       │                                  │
       ▼                                  │
Phase 3 (Gold Standard)                   │
       │                                  │
       ▼                                  │
Phase 4 (Pilot Study)                     │
       │                                  │
       ▼                                  │
Phase 5 (Axes 1-4) ───> Phase 6 (Axes 5-10) ───> Phase 7 (Interaction Validation)
```

**Parallelizable:**
- Phase 1 and Phase 2 run in parallel
- Phase 9 and Phase 10 run in parallel (both depend on Phase 8)
- Within Phase 2: task types, metrics, and variants can be developed in parallel
- Within Phase 5/6: individual axis variants can be developed in parallel

---

## Epic 1: Package Scaffolding & Core Models (Phase 1)

**Depends on:** Nothing
**Parallel with:** Epic 2
**Estimated effort:** 1-2 weeks

### Story 1.1: UV Workspace Setup
Create the monorepo structure with UV workspace configuration.

**Files:**
- Create: `pyproject.toml` (workspace root)
- Create: `agent-index/pyproject.toml`
- Create: `agent-evals/pyproject.toml`

**Acceptance criteria:**
- `uv sync` installs both packages
- `agent-evals` can import from `agent-index`
- Both packages have dev dependencies (pytest, ruff, mypy)

### Story 1.2: Pydantic Models — agent-index
Define core data models for the organizer.

**Files:**
- Create: `agent-index/src/agent_index/__init__.py`
- Create: `agent-index/src/agent_index/models.py`
- Create: `agent-index/tests/test_models.py`

**Models:**
- `DocFile` (rel_path, content, size_bytes, token_count, tier, section, priority, content_hash, last_modified, summary, related)
- `DocTree` (files dict, scanned_at, source, total_tokens)
- `TierConfig` (name, instruction, patterns)
- `TransformStep` (type, strategy, model)
- `IndexConfig` (full config with defaults per DESIGN.md lines 186-225)

**Acceptance criteria:**
- All models validate correctly
- Serialization/deserialization roundtrips work
- Default values match DESIGN.md

### Story 1.3: Config Loading
YAML/TOML config file loading.

**Files:**
- Create: `agent-index/src/agent_index/config.py`
- Create: `agent-index/tests/test_config.py`

**Acceptance criteria:**
- Loads `agent-index.yaml` or `agent-index.toml`
- Validates against `IndexConfig` model
- Error messages point to specific config issues

### Story 1.4: Scanner — Local Files
Scan local directories for documentation files.

**Files:**
- Create: `agent-index/src/agent_index/scanner.py`
- Create: `agent-index/tests/test_scanner.py`

**Acceptance criteria:**
- Produces `DocTree` from local path
- Respects `file_extensions` and `ignore_patterns`
- Computes content hashes for incremental processing
- Handles symlinks safely

### Story 1.5: Scanner — GitHub Repos
Extend scanner for GitHub sources.

**Files:**
- Modify: `agent-index/src/agent_index/scanner.py`
- Create: `agent-index/tests/test_scanner_github.py`

**Acceptance criteria:**
- Fetches docs from public GitHub repos
- Uses GitHub API or raw URLs appropriately
- Caches fetched content
- Handles rate limiting

### Story 1.6: Tier System
Assign files to tiers based on glob patterns.

**Files:**
- Create: `agent-index/src/agent_index/tiers.py`
- Create: `agent-index/tests/test_tiers.py`

**Acceptance criteria:**
- Matches files to tiers via glob patterns
- Priority ordering within tiers works
- Unmatched files go to lowest tier
- BLUF ordering implemented

### Story 1.7: Basic Output Formatter
Generate the tiered AGENTS.md index.

**Files:**
- Create: `agent-index/src/agent_index/output.py`
- Create: `agent-index/tests/test_output.py`

**Acceptance criteria:**
- Produces valid markdown index
- Follows BLUF structure from DESIGN.md lines 329-355
- Path-only format (metadata variants come from evals)
- Injection into existing files via markers

### Story 1.8: CLI Entry Point
Basic CLI with `--local`, `--name` flags.

**Files:**
- Create: `agent-index/src/agent_index/cli.py`
- Modify: `agent-index/pyproject.toml` (add entry point)
- Create: `agent-index/tests/test_cli.py`

**Acceptance criteria:**
- `agent-index --local ./docs --name "Project"` works
- Outputs to stdout or file
- Exit codes: 0 success, 1 error

---

## Epic 2: Eval Framework Core (Phase 2)

**Depends on:** Nothing
**Parallel with:** Epic 1
**Estimated effort:** 3-4 weeks

### Story 2.1: Variant Base Class & Registry
Abstract base for index variants with auto-discovery.

**Files:**
- Create: `agent-evals/src/agent_evals/__init__.py`
- Create: `agent-evals/src/agent_evals/variants/__init__.py`
- Create: `agent-evals/src/agent_evals/variants/base.py`
- Create: `agent-evals/src/agent_evals/variants/registry.py`
- Create: `agent-evals/tests/test_registry.py`

**Acceptance criteria:**
- `IndexVariant` ABC with `metadata()`, `render()`, `setup()`, `teardown()`
- `VariantMetadata` model (name, axis, category, description, token_estimate)
- Registry `load_all()` discovers variants via pkgutil
- `get_variants_for_axis(n)` and `get_all_variants()` work

### Story 2.2: Baseline Variants
Implement the 4 baselines per DESIGN.md lines 488-497.

**Files:**
- Create: `agent-evals/src/agent_evals/variants/baselines.py`
- Create: `agent-evals/tests/test_baselines.py`

**Variants:**
- `NoIndexBaseline` — no docs index at all
- `NoDocsBaseline` — index file only, no actual docs
- `OracleBaseline` — exact relevant docs pre-selected
- `LengthMatchedRandomBaseline` — random docs, same token count

**Acceptance criteria:**
- All 4 baselines render correctly
- Oracle selects correct files from task metadata
- Length-matched samples from doc pool

### Story 2.3: Task Base Class & Loader
Task definition system with YAML loading.

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/__init__.py`
- Create: `agent-evals/src/agent_evals/tasks/base.py`
- Create: `agent-evals/src/agent_evals/tasks/loader.py`
- Create: `agent-evals/tests/test_task_loader.py`

**Acceptance criteria:**
- `EvalTask` ABC with `build_prompt()`, `score_response()`
- Pydantic models for task YAML schemas (base + per-type)
- Loader validates YAML against correct schema by `type` field
- Task ID validation (e.g., `retrieval_001`)

### Story 2.4: Task Types — Core (Types 1-4)

Implement the high-weight task types.

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/retrieval.py` (type 1, weight 0.15)
- Create: `agent-evals/src/agent_evals/tasks/fact_extraction.py` (type 2, weight 0.15)
- Create: `agent-evals/src/agent_evals/tasks/code_generation.py` (type 3, weight 0.15)
- Create: `agent-evals/src/agent_evals/tasks/agentic.py` (type 4, weight 0.12)
- Create: `agent-evals/tests/test_task_types_core.py`

**Acceptance criteria:**
- Each type implements `build_prompt()` and `score_response()`
- YAML schemas match DESIGN.md lines 444-454
- Retrieval uses F-beta (beta=2)
- Agentic tasks support tool-call simulation

### Story 2.5: Task Types — Secondary (Types 5-8)

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/multi_hop.py` (type 5, weight 0.10)
- Create: `agent-evals/src/agent_evals/tasks/negative.py` (type 6, weight 0.08)
- Create: `agent-evals/src/agent_evals/tasks/compositional.py` (type 7, weight 0.07)
- Create: `agent-evals/src/agent_evals/tasks/robustness.py` (type 8, weight 0.06)
- Create: `agent-evals/tests/test_task_types_secondary.py`

**Acceptance criteria:**
- Multi-hop supports `paragraphs` and `question_decomposition`
- Negative tasks enforce `answerable: false`
- Robustness references `base_task_id`

### Story 2.6: Task Types — Edge Cases (Types 9-11)

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/disambiguation.py` (type 9, weight 0.05)
- Create: `agent-evals/src/agent_evals/tasks/conflicting.py` (type 10, weight 0.04)
- Create: `agent-evals/src/agent_evals/tasks/efficiency.py` (type 11, weight 0.03)
- Create: `agent-evals/tests/test_task_types_edge.py`

**Acceptance criteria:**
- Disambiguation includes `interpretations` list
- Conflicting info has `sources` with `authority_level`
- Efficiency-constrained has `token_budget`, `message_limit`

### Story 2.7: Metrics — Core
Cross-cutting metrics per DESIGN.md lines 601-610.

**Files:**
- Create: `agent-evals/src/agent_evals/metrics/__init__.py`
- Create: `agent-evals/src/agent_evals/metrics/base.py`
- Create: `agent-evals/src/agent_evals/metrics/faithfulness.py`
- Create: `agent-evals/src/agent_evals/metrics/tool_calls.py`
- Create: `agent-evals/src/agent_evals/metrics/first_attempt.py`
- Create: `agent-evals/tests/test_metrics.py`

**Acceptance criteria:**
- Faithfulness uses NLI-based claim decomposition (RAGAS-style)
- Tool call counter tracks file reads/searches
- First-attempt success boolean per task

### Story 2.8: Metrics — Navigation & Consistency

**Files:**
- Create: `agent-evals/src/agent_evals/metrics/abstention.py`
- Create: `agent-evals/src/agent_evals/metrics/navigation.py`
- Create: `agent-evals/src/agent_evals/metrics/consistency.py`
- Modify: `agent-evals/tests/test_metrics.py`

**Acceptance criteria:**
- Abstention tracks correct/incorrect abstention rates
- Navigation path quality compares to optimal path
- Consistency measures pairwise similarity across N repetitions

### Story 2.9: LiteLLM Client Wrapper

**Files:**
- Create: `agent-evals/src/agent_evals/llm/__init__.py`
- Create: `agent-evals/src/agent_evals/llm/client.py`
- Create: `agent-evals/tests/test_llm_client.py`

**Acceptance criteria:**
- Thin wrapper around `litellm.completion()`
- OpenRouter provider configuration with `extra_body`
- Provider pinning (`order`, `allow_fallbacks`, `data_collection`)
- Returns generation metadata (tokens, cost)

### Story 2.10: Response Cache

**Files:**
- Create: `agent-evals/src/agent_evals/llm/cache.py`
- Create: `agent-evals/tests/test_cache.py`

**Acceptance criteria:**
- Disk cache keyed on SHA-256 per DESIGN.md lines 827-834
- `--no-cache` flag support
- `--cache-ttl` option (default 30 days)
- LRU eviction with configurable size
- `cache_version` for manual invalidation

### Story 2.11: Token Counter

**Files:**
- Create: `agent-evals/src/agent_evals/llm/token_counter.py`
- Create: `agent-evals/tests/test_token_counter.py`

**Acceptance criteria:**
- Uses LiteLLM's `token_counter(model, text)`
- Fallback to ~4 chars/token heuristic
- Reports prompt vs completion tokens

### Story 2.12: Scoring — Composite & Statistics

**Files:**
- Create: `agent-evals/src/agent_evals/scoring.py`
- Create: `agent-evals/tests/test_scoring.py`

**Acceptance criteria:**
- Composite score: `sum(weight_i × score_i)` per DESIGN.md lines 614-618
- Pairwise Wilcoxon signed-rank with Holm-Bonferroni
- 95% bootstrap CIs (BCa method, 10k resamples)
- Effect size as rank-biserial correlation

### Story 2.13: Eval Runner Core

**Files:**
- Create: `agent-evals/src/agent_evals/runner.py`
- Create: `agent-evals/tests/test_runner.py`

**Acceptance criteria:**
- Runs tasks across variants
- N repetitions per trial (default 10)
- Concurrent API connections (`--max-connections`)
- Progress display (rich/plain/none)

### Story 2.14: Eval Runner CLI

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py`
- Create: `agent-evals/src/agent_evals/cli.py`
- Modify: `agent-evals/pyproject.toml` (entry point)
- Create: `agent-evals/tests/test_cli.py`

**Acceptance criteria:**
- All CLI flags from DESIGN.md lines 861-882 implemented
- Config file loading (`eval-config.yaml`)
- Environment variable support (`AGENT_EVALS_` prefix)
- Precedence: CLI > env vars > config

### Story 2.15: Fixtures — Sample Docs

**Files:**
- Create: `agent-evals/src/agent_evals/fixtures/sample_docs/` (15-25 files)
- Create: `agent-evals/src/agent_evals/fixtures/doc_tree.json`

**Acceptance criteria:**
- Framework API docs domain (15-25 files)
- Project repo docs domain (realistic synthetic)
- Skills/workflows domain (procedural)
- `doc_tree.json` loadable as `DocTree`

### Story 2.16: Cost Estimation & Budget Guardrails

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py`
- Modify: `agent-evals/src/agent_evals/llm/client.py`

**Acceptance criteria:**
- Token-based cost calculation per DESIGN.md lines 739-742
- `--dry-run` estimates without API calls
- `--max-cost` budget cap with 2x pause
- Per-axis cost reporting

---

## Epic 3: Gold Standard & Scorer Calibration (Phase 3)

**Depends on:** Epic 2 (task types, metrics)
**Estimated effort:** 2-3 weeks (human annotation intensive)

### Story 3.1: Gold Standard Data Structure

**Files:**
- Create: `agent-evals/gold_standard/schema.yaml`
- Create: `agent-evals/gold_standard/README.md`

**Acceptance criteria:**
- Schema for gold examples (task_id, human_score, human_rationale)
- Directory structure per task type
- Difficulty distribution documented (easy/medium/hard/edge)

### Story 3.2: Annotation Protocol Document

**Files:**
- Create: `agent-evals/gold_standard/annotation_protocol.md`

**Acceptance criteria:**
- Instructions for human annotators
- Rubric for each task type
- Inter-annotator agreement process (20% overlap)

### Story 3.3: Gold Standard — Core Task Types (1-4)
30-50 gold examples per type × 4 types = 120-200 examples.

**Files:**
- Create: `agent-evals/gold_standard/retrieval/*.yaml`
- Create: `agent-evals/gold_standard/fact_extraction/*.yaml`
- Create: `agent-evals/gold_standard/code_generation/*.yaml`
- Create: `agent-evals/gold_standard/agentic/*.yaml`

**Acceptance criteria:**
- 30-50 examples per type
- Difficulty spread: 30% easy, 40% medium, 20% hard, 10% edge
- Inter-annotator kappa >= 0.70

### Story 3.4: Gold Standard — Secondary Task Types (5-8)

**Files:**
- Create: `agent-evals/gold_standard/multi_hop/*.yaml`
- Create: `agent-evals/gold_standard/negative/*.yaml`
- Create: `agent-evals/gold_standard/compositional/*.yaml`
- Create: `agent-evals/gold_standard/robustness/*.yaml`

### Story 3.5: Gold Standard — Edge Case Task Types (9-11)

**Files:**
- Create: `agent-evals/gold_standard/disambiguation/*.yaml`
- Create: `agent-evals/gold_standard/conflicting/*.yaml`
- Create: `agent-evals/gold_standard/efficiency/*.yaml`

### Story 3.6: LLM-as-Judge Calibration

**Files:**
- Create: `agent-evals/src/agent_evals/judge/__init__.py`
- Create: `agent-evals/src/agent_evals/judge/calibrator.py`
- Create: `agent-evals/tests/test_judge_calibration.py`

**Acceptance criteria:**
- Judge vs gold: Cohen's kappa >= 0.70
- Spearman rho >= 0.80 on score ordering
- Kendall's tau alongside Spearman
- 150+ human-annotated examples used

### Story 3.7: Sentinel Tasks

**Files:**
- Create: `agent-evals/task_data/sentinels/*.yaml`

**Acceptance criteria:**
- 5-10 trivially easy tasks per domain
- Known answers, deterministic scoring
- Used for temporal drift detection

### Story 3.8: Canary Tasks

**Files:**
- Create: `agent-evals/task_data/canaries/*.yaml`

**Acceptance criteria:**
- Trivial answers that verify scoring pipeline
- End-to-end validation of scorer

---

## Epic 4: Pilot Study (Phase 4)

**Depends on:** Epic 3 (gold standard)
**Estimated effort:** 1 week

### Story 4.1: Pilot Configuration

**Files:**
- Create: `agent-evals/pilot/config.yaml`

**Acceptance criteria:**
- 10 tasks per task type (110 total)
- N=3 repetitions (for quick iteration)
- Two alternative axis orderings defined

### Story 4.2: Axis Ordering Sensitivity Test

**Files:**
- Create: `agent-evals/pilot/ordering_test.py`

**Acceptance criteria:**
- Tests default ordering vs alternative
- Reports if winners differ
- Flags need for expanded interaction validation

### Story 4.3: Prompt Framing Comparison

**Files:**
- Create: `agent-evals/pilot/framing_test.py`

**Acceptance criteria:**
- Constant framing (same system prompt for all variants)
- Adapted framing (variant-specific guidance)
- Reports which performs better per axis

### Story 4.4: Saturation Check

**Files:**
- Create: `agent-evals/pilot/saturation.py`

**Acceptance criteria:**
- Plots learning curve: score stability vs task count
- Reports saturation point
- Validates 330+ tasks is sufficient

---

## Epic 5: Eval Axes 1-4 (Phase 5)

**Depends on:** Epic 4 (pilot results)
**Estimated effort:** 2-3 weeks

### Story 5.1: Axis 1 Variants — Structure

**Files:**
- Create: `agent-evals/src/agent_evals/variants/structure_flat.py`
- Create: `agent-evals/src/agent_evals/variants/structure_2tier.py`
- Create: `agent-evals/src/agent_evals/variants/structure_3tier.py`
- Create: `agent-evals/src/agent_evals/variants/structure_4tier.py`
- Create: `agent-evals/src/agent_evals/variants/structure_inline_required.py`

**Acceptance criteria:**
- 5 structure variants implemented
- Each variant's `metadata().axis == 1`
- Beam search retains top 2-3 candidates

### Story 5.2: Axis 2 Variants — Pointer Metadata

**Files:**
- Create: `agent-evals/src/agent_evals/variants/metadata_path_only.py`
- Create: `agent-evals/src/agent_evals/variants/metadata_with_summary.py`
- Create: `agent-evals/src/agent_evals/variants/metadata_with_tokens.py`
- Create: `agent-evals/src/agent_evals/variants/metadata_with_related.py`

**Acceptance criteria:**
- 4 metadata variants implemented
- Tests against Axis 1 beam winners
- Each variant's `metadata().axis == 2`

### Story 5.3: Axis 3 Variants — Format Family

**Files:**
- Create: `agent-evals/src/agent_evals/variants/format_pipe_delimited.py`
- Create: `agent-evals/src/agent_evals/variants/format_yaml.py`
- Create: `agent-evals/src/agent_evals/variants/format_markdown_list.py`
- Create: `agent-evals/src/agent_evals/variants/format_markdown_table.py`
- Create: `agent-evals/src/agent_evals/variants/format_plain_markdown.py`

**Acceptance criteria:**
- 5 format variants implemented
- Each variant's `metadata().axis == 3`

### Story 5.4: Axis 4 Variants — Position Strategy

**Files:**
- Create: `agent-evals/src/agent_evals/variants/position_natural.py`
- Create: `agent-evals/src/agent_evals/variants/position_bluf.py`
- Create: `agent-evals/src/agent_evals/variants/position_edges.py`
- Create: `agent-evals/src/agent_evals/variants/position_random.py`

**Acceptance criteria:**
- 4 position variants implemented
- Each variant's `metadata().axis == 4`

### Story 5.5: Beam Search Implementation

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py`
- Create: `agent-evals/src/agent_evals/beam_search.py`

**Acceptance criteria:**
- Retains candidates within statistical parity (Wilcoxon p > 0.10)
- Typical beam width 2-4 per axis
- Tracks beam history for reports

### Story 5.6: Sensitivity Analysis — Weight Schemes

**Files:**
- Modify: `agent-evals/src/agent_evals/scoring.py`

**Acceptance criteria:**
- 5 weight schemes per DESIGN.md lines 479-484
- Default, retrieval-heavy, code-heavy, agentic-heavy, uniform
- Reports if winner changes across schemes

---

## Epic 6: Eval Axes 5-10 (Phase 6)

**Depends on:** Epic 5 (beam winners from axes 1-4)
**Estimated effort:** 3-4 weeks

### Story 6.1: Axis 5 Variants — Doc Transformation

**Files:**
- Create: `agent-evals/src/agent_evals/variants/transform_passthrough.py`
- Create: `agent-evals/src/agent_evals/variants/transform_algorithmic.py`
- Create: `agent-evals/src/agent_evals/variants/transform_llm_compressed.py`
- Create: `agent-evals/src/agent_evals/variants/transform_restructured.py`
- Create: `agent-evals/src/agent_evals/variants/transform_tagged.py`

### Story 6.2: Axis 6 Variants — Index Scale

**Files:**
- Create: `agent-evals/src/agent_evals/variants/scale_5.py`
- Create: `agent-evals/src/agent_evals/variants/scale_15.py`
- Create: `agent-evals/src/agent_evals/variants/scale_50.py`
- Create: `agent-evals/src/agent_evals/variants/scale_100.py`
- Create: `agent-evals/src/agent_evals/variants/scale_200.py`

**Note:** Requires expanded fixture set for 200 entries.

### Story 6.3: Axis 7 Variants — Signal-to-Noise

**Files:**
- Create: `agent-evals/src/agent_evals/variants/noise_0.py`
- Create: `agent-evals/src/agent_evals/variants/noise_25.py`
- Create: `agent-evals/src/agent_evals/variants/noise_50.py`
- Create: `agent-evals/src/agent_evals/variants/noise_75.py`

**Note:** Requires distractor entry generation.

### Story 6.4: Axis 8 Variants — Entry Granularity

**Files:**
- Create: `agent-evals/src/agent_evals/variants/granularity_file.py`
- Create: `agent-evals/src/agent_evals/variants/granularity_section.py`
- Create: `agent-evals/src/agent_evals/variants/granularity_function.py`
- Create: `agent-evals/src/agent_evals/variants/granularity_mixed.py`

### Story 6.5: Axis 9 Variants — Cross-Reference Density

**Files:**
- Create: `agent-evals/src/agent_evals/variants/xref_none.py`
- Create: `agent-evals/src/agent_evals/variants/xref_light.py`
- Create: `agent-evals/src/agent_evals/variants/xref_dense.py`

### Story 6.6: Axis 10 Variants — Temporal Markers

**Files:**
- Create: `agent-evals/src/agent_evals/variants/temporal_none.py`
- Create: `agent-evals/src/agent_evals/variants/temporal_version.py`
- Create: `agent-evals/src/agent_evals/variants/temporal_modified.py`
- Create: `agent-evals/src/agent_evals/variants/temporal_deprecated.py`

---

## Epic 7: Interaction Validation (Phase 7)

**Depends on:** Epic 6 (beam winners from all 10 axes)
**Estimated effort:** 2 weeks

### Story 7.1: Factorial Design Generator

**Files:**
- Create: `agent-evals/src/agent_evals/factorial.py`

**Acceptance criteria:**
- 2^(5-1) Resolution V fractional factorial (16 runs)
- Generator: E = ABCD
- Pre-registered pruning criteria

### Story 7.2: Interaction Effect Analysis

**Files:**
- Create: `agent-evals/src/agent_evals/interaction_analysis.py`

**Acceptance criteria:**
- Lenth method for identifying significant interactions
- Half-normal plots
- Override detection (p < 0.05 vs sequential winner)

### Story 7.3: Final Comparison with PoLL

**Files:**
- Modify: `agent-evals/src/agent_evals/judge/`

**Acceptance criteria:**
- 3-model panel: GPT-4o-mini + Claude 4.5 Haiku + Gemini 3 Flash
- Aggregate by averaging
- Used for final comparison only

---

## Epic 8: Organizer Tier System (Phase 8)

**Depends on:** Epic 7 (winning format determined)
**Estimated effort:** 1-2 weeks

### Story 8.1: Apply Winning Format to Output

**Files:**
- Modify: `agent-index/src/agent_index/output.py`

**Acceptance criteria:**
- Default format matches eval winner
- Configurable fallback to other formats

### Story 8.2: Cross-Tool Output — CLAUDE.md

**Files:**
- Modify: `agent-index/src/agent_index/output.py`

**Acceptance criteria:**
- Claude Code-specific format generation
- `output_targets: ["claude.md"]` works

### Story 8.3: Cross-Tool Output — Cursor Rules

**Files:**
- Modify: `agent-index/src/agent_index/output.py`

**Acceptance criteria:**
- `.cursor/rules/*.mdc` generation
- YAML frontmatter with glob patterns

### Story 8.4: Cross-Tool Output — Copilot Instructions

**Files:**
- Modify: `agent-index/src/agent_index/output.py`

**Acceptance criteria:**
- `.github/copilot-instructions.md` generation

---

## Epic 9: Doc Transformation Pipeline (Phase 9)

**Depends on:** Epic 8
**Parallel with:** Epic 10
**Estimated effort:** 2-3 weeks

### Story 9.1: Transform Pipeline Core

**Files:**
- Create: `agent-index/src/agent_index/transform.py`
- Create: `agent-index/tests/test_transform.py`

**Acceptance criteria:**
- Composable pipeline: steps execute sequentially
- Passthrough, algorithmic, LLM strategies
- State saved to `.agent-index-state.json`

### Story 9.2: Algorithmic Transform — Compressed

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- Regex/heuristic cleanup
- No LLM needed
- Removes boilerplate, normalizes formatting

### Story 9.3: LLM Transform — Compressed

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- LLM rewrites for conciseness
- Respects 10% compression threshold (ShortenDoc finding)

### Story 9.4: LLM Transform — Restructured

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- LLM reorders: signatures first, parameters in tables
- Optimized for lookup patterns

### Story 9.5: LLM Transform — Tagged

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- LLM compresses + adds semantic markers
- Markers aid retrieval

### Story 9.6: Incremental Transform

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- Only re-transforms files whose hash changed
- State persisted across runs

### Story 9.7: Transform Error Handling

**Files:**
- Modify: `agent-index/src/agent_index/transform.py`

**Acceptance criteria:**
- Per-file retry with exponential backoff (max 3)
- Fallback to passthrough on permanent failure
- Partial results preserved (36 of 37 complete = 36 saved)
- Resumable from state file

---

## Epic 10: UX Features (Phase 10)

**Depends on:** Epic 8
**Parallel with:** Epic 9
**Estimated effort:** 2 weeks

### Story 10.1: Auto-Detect Mode

**Files:**
- Modify: `agent-index/src/agent_index/cli.py`

**Acceptance criteria:**
- `--auto-detect` scans project
- Heuristics: "getting-started" → required, API reference → recommended
- Produces editable YAML config

### Story 10.2: Interactive Wizard

**Files:**
- Create: `agent-index/src/agent_index/wizard.py`
- Modify: `agent-index/src/agent_index/cli.py`

**Acceptance criteria:**
- `--init` launches questionnaire
- Prompts: project name, doc locations, tiers, commands, rules
- Outputs complete `agent-index.yaml`

### Story 10.3: Scaffold Mode

**Files:**
- Create: `agent-index/src/agent_index/scaffold.py`
- Modify: `agent-index/src/agent_index/cli.py`

**Acceptance criteria:**
- `--scaffold` creates directory structure
- Placeholder `.llms.md` files per tier

### Story 10.4: CI Validation Mode

**Files:**
- Create: `agent-index/src/agent_index/validate.py`
- Modify: `agent-index/src/agent_index/cli.py`

**Acceptance criteria:**
- `--validate` compares generated index vs actual docs
- Reports: missing files, extra files, stale entries
- Non-zero exit on drift

### Story 10.5: Pre-Commit Hook

**Files:**
- Create: `agent-index/.pre-commit-hooks.yaml`

**Acceptance criteria:**
- Hook runs `agent-index --validate`
- Blocks commit on drift

---

## Parallel Work Summary

| Phase | Can Run In Parallel With |
|-------|-------------------------|
| 1 (agent-index core) | Phase 2 |
| 2 (agent-evals core) | Phase 1 |
| 9 (transform pipeline) | Phase 10 |
| 10 (UX features) | Phase 9 |

**Within Phase 2 (agent-evals core):**
- Stories 2.4, 2.5, 2.6 (task types) can run in parallel
- Stories 2.7, 2.8 (metrics) can run in parallel
- Stories 2.9, 2.10, 2.11 (LLM client, cache, tokens) can run in parallel

**Within Phase 3 (gold standard):**
- Stories 3.3, 3.4, 3.5 (gold examples per type) can run in parallel

**Within Phase 5/6 (eval axes):**
- Individual axis variant stories can run in parallel once beam search infra exists

---

## Critical Path

```
Phase 1/2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → (9 & 10)
```

**Minimum time to results (assuming parallelization):**
- Phases 1+2: 3-4 weeks (parallel)
- Phase 3: 2-3 weeks (annotation bottleneck)
- Phase 4: 1 week
- Phase 5: 2-3 weeks
- Phase 6: 3-4 weeks
- Phase 7: 2 weeks
- Phase 8: 1-2 weeks
- Phases 9+10: 2-3 weeks (parallel)

**Total: ~16-22 weeks** to complete organizer with eval-determined format.

---

## Execution Approach

**Recommended:** Use superpowers:subagent-driven-development for implementation.

Each epic can be a sprint. Within each epic, independent stories can be dispatched to parallel subagents. Code review between stories ensures quality.

Ready to begin?
