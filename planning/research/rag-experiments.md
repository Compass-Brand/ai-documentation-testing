# Research: somasays/rag-experiments

Source: https://github.com/somasays/rag-experiments
License: MIT
Stars: 4 | Created: 2026-01-22 | Commits: 2 (not actively maintained)

## What It Contains

4 chunking strategies: token, sentence, recursive, semantic
2 datasets: HotpotQA (3K-9K char docs), Natural Questions (25K-85K char docs)
RAGAS evaluation: context_recall, context_precision, faithfulness, answer_relevancy
Pipeline: YAML Config -> Dataset -> Chunking -> ChromaDB -> Top-K retrieval -> LLM gen -> RAGAS eval

## Key Finding

**Chunk SIZE dominates over chunk STRATEGY.** Token chunking at 3000 chars (recall 0.975) dramatically outperforms token at 1000 chars (recall 0.775), while different strategies at the same size perform similarly.

## Reusable Components

1. **Strategy registry pattern** - `STRATEGIES` dict + `get_strategy()` factory. Clean, extensible. Our variant registry should follow this.
2. **RAGAS evaluator wrapper** - `evaluate()` accepts `{question, answer, ground_truth, contexts}`. Directly reusable for faithfulness/groundedness metrics.
3. **Experiment runner** - YAML-driven configs, checkpointing, per-query results. Good architecture to reference.
4. **Dataset abstraction** - `Dataset` ABC with `load()` interface. We need our own loaders but the pattern is right.

## Not Reusable

- Datasets (QA benchmarks, not documentation)
- Pre-computed results (specific to their experiments)
- Analysis module (tightly coupled to their experiments)
- Only dense vector retrieval (no BM25/hybrid despite having it as a dependency)

## Relevance to Axis 8 (Entry Granularity)

Partially relevant. Tests chunk SIZE but NOT semantic granularity (page vs section vs function). Does not evaluate hierarchical chunking or document-structure-aware strategies. Key insight: at the same actual size, strategies perform similarly, so granularity testing should focus on what the entry POINTS TO (file vs section vs function), not chunking algorithm.
