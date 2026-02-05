# Research: Empirically-Justified Task Weights

## Methodology

Weights calibrated using three principles from research:
1. **Production frequency** — how often this task type arises in real agent usage
2. **Failure criticality** — how damaging is failure at this task
3. **Difficulty calibration** — how hard is this for current models (AgentBench reciprocal-average principle)

## Key Data Points

### Agent Action Distribution (SWE-Pruner, Claude Sonnet 4.5)
- Read operations (file/directory inspection): **76.1% of tokens**
- Execute operations (testing): **12.1% of tokens**
- Edit operations (code changes): **11.8% of tokens**

### Real-World Agent PR Distribution
- Bug fixes: 31.0%
- Feature development: 26.8%
- Refactoring: 24.9%
- Documentation: 22.1%
- Testing: 18.8%

### Agent Context File Content (2,303 files from 1,925 repos)
- Testing instructions: 75.0%
- Implementation details: 69.9%
- Architecture: 67.7%
- Development process: 63.3%
- Build and run: 62.3%

### Multi-Hop Degradation
- BM25 retrieval accuracy: 53.7% (single-hop) -> 25.9% (multi-hop) on HotpotQA
- MuSiQue: 30-point F1 drop for single-hop models on multi-hop questions
- Multi-hop performance collapses to weakest evidence link

### Abstention
- AbstentionBench: reasoning-tuned models show 24% drop in abstention vs non-reasoning
- The models most used for coding agents are worst at knowing when they don't know

### RAGAS Baseline
- 4 equally-weighted metrics (50% retrieval, 50% generation)
- RAG pipeline is only as performant as its weakest component

## Recommended Weights

| # | Task Type | Weight | Key Justification |
|---|-----------|--------|-------------------|
| 1 | Retrieval | 0.15 | 76.1% of agent tokens are read/search. Gating task for all others. |
| 2 | Fact extraction | 0.15 | RAG FP4 (not extracted) is primary failure mode. 69.9% of context files are implementation details. |
| 3 | Code generation | 0.15 | Primary high-stakes output. 31% bug fixes + 26.8% features in agent PRs. |
| 4 | End-to-end agentic | 0.12 | Integration test for full pipeline. Overlaps with core three so slightly lower. |
| 5 | Multi-hop reasoning | 0.10 | 25-30 point accuracy drops. SWE-Bench solutions average 4.1 files. |
| 6 | Negative/unanswerable | 0.08 | 24% worse abstention in reasoning models. Critical for trust. |
| 7 | Compositional code gen | 0.07 | Compounding error rates. Multi-API synthesis is standard. |
| 8 | Robustness/perturbation | 0.06 | Up to 40pp degradation. Important for production reliability. |
| 9 | Disambiguation | 0.05 | Silent errors on ambiguous queries. Less frequent in production. |
| 10 | Conflicting info | 0.04 | Edge case in maintained docs. Necessary for multi-source indexes. |
| 11 | Efficiency-constrained | 0.03 | Constraint on execution, not distinct capability. |
| **Total** | | **1.00** | |

## Weight Tiers

**Tier 1 — Core capabilities (0.15 each, 45%):** Retrieval, Fact Extraction, Code Generation. Fundamental RAG pipeline.

**Tier 2 — Integration and difficulty (0.10-0.12, 22%):** End-to-end Agentic, Multi-hop Reasoning. Capability composition. Hard tasks get extra weight per AgentBench reciprocal-average principle.

**Tier 3 — Robustness and edge cases (0.03-0.08, 33%):** Remaining six types. Negative queries highest in tier (0.08) due to hallucination risk.

## Sources

- Vercel AGENTS.md evals: 100% vs 79% for skills, 56% skill non-invocation
- SWE-Pruner action distribution (Claude Sonnet 4.5): 76/12/12 read/execute/edit
- SWE-Bench Pro: solutions avg 107.4 lines across 4.1 files
- RAGAS: equal-weight retrieval/generation metrics
- Seven Failure Points in RAG (arXiv 2401.05856): 3 retrieval + 4 generation failures
- Agent READMEs empirical study (arXiv 2511.12884): 2,303 context files analyzed
- Agentic Coding PRs study (arXiv 2509.14745): real-world PR distribution
- AgentBench (ICLR 2024): reciprocal-average scoring
- MCP-AgentBench (arXiv 2509.09734): uniform complexity distribution
- AbstentionBench (arXiv 2506.09038): reasoning model abstention failure
- Multi-hop weakest link law (arXiv 2601.12499): position bias effects
- Robustness benchmarks (arXiv 2601.06341): perturbation impact
- MuSiQue (TACL 2022): multi-hop composition degradation
- Anthropic eval guidance: grade outcomes not paths, test negative cases
