# Planning directory

Research and design artifacts for the AI Documentation Testing project.

## Structure

```text
planning/
  README.md              # This file
  DESIGN.md              # Master design document
  TRACKER.md             # Task tracker for design fixes
  ROUND1_FINDINGS.md     # Initial research findings
  research/              # Research findings and decisions
    task-weights.md      # Empirical justification for eval task weights
    reusable-benchmarks.md # Open-source benchmarks we can adapt
    openrouter-config.md # OpenRouter + LiteLLM configuration guide
    rag-experiments.md   # Findings from somasays/rag-experiments
    datasets.md          # Dataset recommendations per task type
```

## Workflow

1. Research goes in `research/` as findings accumulate
2. `DESIGN.md` is the canonical design specification
3. `TRACKER.md` tracks implementation progress
