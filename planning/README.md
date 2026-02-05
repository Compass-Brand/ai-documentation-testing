# Planning Directory

Organized planning artifacts for the Agent Knowledge Organizer project.

## Structure

```
planning/
  README.md              # This file
  DESIGN.md              # Master design document (776 lines)
  TRACKER.md             # Master task tracker for all design fixes
  phases/                # Implementation phase plans
    phase-1-scaffolding.md
    phase-2-eval-framework.md
    ...
  research/              # Research findings and decisions
    task-weights.md      # Empirical justification for eval task weights
    reusable-benchmarks.md # Open-source benchmarks we can adapt
    openrouter-config.md # OpenRouter + LiteLLM configuration guide
    rag-experiments.md   # Findings from somasays/rag-experiments
    datasets.md          # Dataset recommendations per task type (30+ surveyed)
  decisions/             # Architecture Decision Records
    001-statistical-methodology.md
    002-scoring-approach.md
    ...
```

## Workflow

1. Research goes in `research/` as findings accumulate
2. Decisions get recorded in `decisions/` as ADRs
3. Phase plans in `phases/` track implementation order
4. `TRACKER.md` is the single source of truth for progress
