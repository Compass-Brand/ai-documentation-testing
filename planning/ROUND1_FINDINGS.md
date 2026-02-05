# Round 1 Findings Report: DESIGN.md Technical Review

**Date:** 2026-02-05
**Scope:** Factual/technical verification via web search, Context7, and HuggingFace tools
**Reviewers:** 5 parallel subagents (R1-A through R1-E)

---

## Executive Summary

| Category | Count |
|----------|-------|
| **Critical Issues (must fix)** | 8 |
| **Warnings (should fix)** | 21 |
| **Suggestions (nice to have)** | 15 |
| **Items verified correct** | 50+ |

---

## Critical Issues (Must Fix)

### 1. OpenRouter Model IDs Use Dots, Not Hyphens
**Location:** Lines 667, 800, 847-848
**Problem:** `openrouter/anthropic/claude-opus-4-5` should be `openrouter/anthropic/claude-opus-4.5` (dot before 5, not hyphen).
**Fix:** Change all OpenRouter model references from `claude-opus-4-5` and `claude-sonnet-4-5` to `claude-opus-4.5` and `claude-sonnet-4.5`.

### 2. UV Workspace Syntax Incomplete
**Location:** Line 44
**Problem:** Doc shows `agent-index = { workspace = true }` as a single declaration. UV actually requires TWO parts:
```toml
# In agent-evals/pyproject.toml
[project]
dependencies = ["agent-index"]

[tool.uv.sources]
agent-index = { workspace = true }
```
Plus root `pyproject.toml` needs:
```toml
[tool.uv.workspace]
members = ["agent-index", "agent-evals"]
```
**Fix:** Add the complete UV workspace configuration example.

### 3. tiktoken Inaccurate for Non-OpenAI Models
**Location:** Line 902
**Problem:** tiktoken only provides accurate counts for OpenAI models. For Claude, Mistral, Gemini, the estimates will be 10-20% off.
**Fix:** Replace `tiktoken (if available) or ~4 chars/token heuristic` with `LiteLLM's token_counter(model, text)` which dispatches to the correct tokenizer per model.

### 4. nlpaug Is Abandoned
**Location:** Line 779, research/datasets.md
**Problem:** nlpaug last release was July 7, 2022 (3.5+ years ago). Effectively unmaintained.
**Fix:** Remove nlpaug from the tool list. Use `PromptBench + TextAttack.augmentation` instead — they cover all the same perturbation types.

### 5. Cohen's Kappa Threshold Inconsistent and Mislabeled
**Location:** Lines 621 vs 647
**Problem:** Line 621 targets `kappa > 0.70`, line 647 targets `kappa >= 0.60`. Also, 0.60 is "moderate agreement" (Landis-Koch), not "substantial" — substantial starts at 0.61.
**Fix:** Resolve to a single target (recommend >= 0.65 or >= 0.70) and use correct Landis-Koch terminology.

### 6. arXiv 2601.20404 Mischaracterized as "Inline" Study
**Location:** Line 914
**Problem:** The paper tests AGENTS.md presence vs absence, NOT inline vs pointer formats. Saying "inline AGENTS.md" mischaracterizes the finding.
**Fix:** Change "28.64% time reduction with inline AGENTS.md" to "28.64% median runtime reduction with AGENTS.md present (vs. absent)". Update "Informs" column from "Inline vs pointer eval" to "Value of any index file".

### 7. 42%/72% Code Judge Accuracy Has No Citation
**Location:** Line 644
**Problem:** The claim about LLM judge accuracy on code correctness cites no source.
**Fix:** Add citation: "Findeis et al. 2025, via He et al. 'From Code to Courtroom' arXiv 2503.02246".

### 8. RAGAS API Migration
**Location:** Implied (metrics section references RAGAS)
**Problem:** RAGAS API has changed from `from ragas.metrics import faithfulness` to `from ragas.metrics.collections import Faithfulness` (class-based).
**Fix:** If using RAGAS directly, update to the collections-based API. Pin RAGAS version in pyproject.toml.

---

## Warnings (Should Fix)

### Libraries & APIs (R1-A)

| # | Issue | Location | Action |
|---|-------|----------|--------|
| W1 | `extra_body` defined but not shown passed to `litellm.completion()` | Lines 674-683 | Show complete call with `extra_body=extra_body` kwarg |
| W2 | Provider names may need capitalization (`"Anthropic"` not `"anthropic"`) | Line 678 | Verify against OpenRouter API |
| W3 | "No OpenAI compatibility shim" is misleading | Line 249 | Reword: LiteLLM presents OpenAI-compatible interface but calls native APIs internally |
| W4 | GPT-5.1 may not be a real model | Line 691 | Verify against OpenRouter; may need `GPT-5.2` instead |
| W5 | PoLL panel models outdated (Claude 3.5 Haiku, Gemini 1.5 Flash) | Line 635 | Update to Claude 4.5 Haiku and Gemini 3 Flash |

### Statistics (R1-B)

| # | Issue | Location | Action |
|---|-------|----------|--------|
| W6 | No formal power analysis for N=10/N=16 | Line 442 | Add simulation-based power calculation with explicit effect size |
| W7 | Beam search "within 2 points" threshold arbitrary | Lines 474-479 | Replace with statistical criterion (e.g., p > 0.10 on pairwise Wilcoxon) |
| W8 | Interaction validation pruning is ad-hoc | Lines 488-491 | Use proper 2^(5-1) Resolution V fractional factorial (16 runs) |

### Datasets (R1-C)

| # | Issue | Location | Action |
|---|-------|----------|--------|
| W9 | SWE-bench Verified license listed as "--" | Line 775 | Update to "MIT (code)" with footnote about dataset content licenses |
| W10 | WikiContradict only has 253 examples | Line 781 | Add footnote noting augmentation with synthetic conflicts + ConflictBank |
| W11 | TextAttack aging (last release March 2024) | Line 779 | Pin to v0.3.10 and validate on target Python version |
| W12 | RAGBench HF size tag inconsistent | Line 784 | Cosmetic; note the HF tag says "10K<n<100K" but paper claims 100K |

### Infrastructure (R1-D)

| # | Issue | Location | Action |
|---|-------|----------|--------|
| W13 | OpenRouter `order` + `allow_fallbacks: false` has reliability issues | Lines 674-681 | Consider using `only: ["anthropic"]` instead |
| W14 | `data_collection: "deny"` not shown inside provider object | Line 698 | Show it inside the `extra_body.provider` dict in code sample |
| W15 | SWE-bench field names are UPPERCASE (`FAIL_TO_PASS`) | Line 425 | Update to uppercase; note fields are JSON strings needing `json.loads()` |
| W16 | Dual HuggingFace IDs for SWE-bench | Line 775 | Note both `princeton-nlp/` and `SWE-bench/` exist; pin to specific version |
| W17 | Inspect AI GitHub org may migrate (UK AISI rebrand) | Research doc | Pin to specific version |

### Research References (R1-E)

| # | Issue | Location | Action |
|---|-------|----------|--------|
| W18 | AgentBench "reciprocal-average" cited as rationale but not used | Line 921 | Clarify it's supporting rationale, not the actual weighting formula |
| W19 | RAGAS "equal-weight" is library default, not paper finding | Line 922 | Attribute to "RAGAS library defaults" not the paper |
| W20 | somasays/rag-experiments is weak source (4 stars, personal repo) | Line 923 | Supplement with peer-reviewed source on chunk size vs strategy |
| W21 | HotpotQA BM25 numbers lack specific citation | task-weights.md | Add specific paper source for 53.7%/25.9% figures |

---

## Suggestions (Nice to Have)

### Libraries & APIs
1. If using RAGAS with LiteLLM/OpenRouter, use `ragas.llms.llm_factory()` with custom `base_url`
2. Consider whether the organizer's LLM config should route through LiteLLM/OpenRouter for consistency
3. Pin RAGAS version in `pyproject.toml` to avoid breaking API changes

### Statistics
4. Specify bootstrap CI method as BCa (bias-corrected and accelerated)
5. Add 2 more weighting schemes: uniform (1/11 each) and agentic-heavy
6. Report Kendall's tau alongside Spearman rho
7. Consider BH-FDR for exploratory beam search phases, Holm for confirmatory

### Datasets
8. Add PromptCraft as backup robustness generator if nlpaug dropped
9. Pin dataset versions to specific HF commits for reproducibility
10. Add "Domain Adaptation Level" column to dataset table

### Infrastructure
11. Note that `/generation` endpoint requires async second API call (not inline)
12. Add root `pyproject.toml` content showing `[tool.uv.workspace]`
13. Leverage Inspect AI's existing SWE-bench integration (`inspect_evals/swe_bench_verified_mini`)
14. Document Docker dependency for SWE-bench evaluation
15. Make explicit decision: custom runner vs building on Inspect AI primitives

---

## Items Verified Correct (Selected Highlights)

### Libraries
- `litellm.completion()` syntax, `api_key` parameter, `openrouter/` prefix
- `extra_body` with `provider.order`, `allow_fallbacks`, `require_parameters`
- All Pydantic v2 patterns: `BaseModel`, `Field`, `default_factory`, `list[str]`, `int | None`
- RAGAS faithfulness = NLI-based claim decomposition

### Statistics
- Wilcoxon N=5 minimum p-value = 0.0625 (mathematically correct)
- Holm-Bonferroni appropriate for pairwise comparisons
- Bootstrap 10,000 resamples is standard
- Rank-biserial correlation correct for Wilcoxon
- Spearman >= 0.80 well-calibrated target

### Datasets
- All 10 HuggingFace dataset IDs exist and are accessible
- 8 of 10 datasets have accurate license, size, and suitability claims
- CodeRAG-Bench, TechQA, MultiHop-RAG, RepLiQA, BigCodeBench, AmbigQA all verified

### Infrastructure
- OpenRouter provider pinning fields verified
- OpenRouter `/generation` endpoint metadata confirmed
- Inspect AI Task/Solver/Scorer architecture accurate
- DeepEval G-Eval and ToolCorrectnessMetric verified
- Pre-commit hook format correct

### Research References
- arXiv 2411.10541 (40% format variance) — accurate
- ShortenDoc 10% compression threshold — accurate
- SWE-Pruner 76/12/12 token distribution — accurate
- AbstentionBench 24% worse abstention — accurate
- Seven Failure Points 3+4 modes — accurate
- Verga et al. PoLL 7-8x cheaper — accurate

---

## Next Steps

1. **Review this report** and approve/reject each finding
2. **I will apply approved fixes** to DESIGN.md
3. **Proceed to Round 2** (flesh out gaps and missing details)

Which findings would you like me to apply?
