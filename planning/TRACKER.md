# Design Fix Tracker

Status: `[ ]` = pending, `[x]` = done, `[~]` = in progress, `[R]` = needs research

## Critical Fixes

- [x] 1. Increase N from 5 to 10+ repetitions (statistical adequacy)
- [x] 2. Fix sequential cascade (beam search, seed configs, revisit protocol)
- [x] 3. Add null/oracle baselines (no-index, no-docs, oracle, length-matched)
- [x] 4. Drop clustered SEs, use domain as fixed/random effect
- [x] 5. Fix fact extraction scoring (LLM-as-judge primary)

## Important Fixes

- [x] 6. Justify axis ordering (pilot study protocol)
- [x] 7. Specify defaults for non-varied dimensions
- [x] 8. Increase agentic tasks to 30+ (330+ total across 11 types)
- [x] 9. Empirically justify task weights (see planning/research/task-weights.md)
- [x] 10. Test both constant and adapted prompt framing
- [x] 11. Clarify human validation scope (30-50 gold standard examples)

## New Axes

- [x] 12. Axis 6: Index Scale / Entry Count
- [x] 13. Axis 7: Signal-to-Noise Ratio (Distractors)
- [x] 14. Axis 8: Entry Granularity (informed by rag-experiments research)
- [x] 15. Axis 9: Cross-Reference Density
- [x] 16. Axis 10: Temporal / Version Markers

## New Task Types

- [x] 17. Multi-Hop Reasoning
- [x] 18. Negative / Unanswerable Queries
- [x] 19. Disambiguation / Ambiguous Queries
- [x] 20. Conflicting Information Resolution
- [x] 21. Robustness Under Query Perturbation
- [x] 22. Efficiency-Constrained Tasks
- [x] 23. Compositional Code Generation

## New Metrics

- [x] 24. Faithfulness / Groundedness
- [x] 25. Tool Call Count
- [x] 26. First-Attempt Success Rate
- [x] 27. Correct Abstention Rate
- [x] 28. Navigation Path Quality
- [x] 29. Consistency

## Infrastructure & Process

- [x] 30. Cost estimation (token-based, not per-call)
- [x] 31. Qualitative Error Analysis Protocol
- [x] 32. Scorer disagreement resolution protocol
- [x] 33. Grade outcomes, not paths
- [x] 34. Transcript review protocol
- [x] 35. Eval saturation monitoring
- [x] 36. Sentinel tasks for temporal drift
- [x] 37. Contamination prevention

## Research (Completed)

- [x] Task weights justification → planning/research/task-weights.md
- [x] Reusable open-source benchmarks → planning/research/reusable-benchmarks.md
- [x] rag-experiments repo analysis → planning/research/rag-experiments.md
- [x] OpenRouter + LiteLLM config → planning/research/openrouter-config.md
