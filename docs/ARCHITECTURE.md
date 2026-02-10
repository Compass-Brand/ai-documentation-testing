# Architecture

This document describes the high-level architecture of the AI Documentation Testing framework, including the evaluation pipeline, package structure, beam search cascade, and variant/task registration flow.

---

## 1. Pipeline Overview

The evaluation pipeline flows from configuration through task execution to final reporting.

```mermaid
flowchart LR
    A[EvalRunConfig] --> B[Load Tasks]
    B --> C[Load Variants]
    C --> D[EvalRunner.run]
    D --> E["Trials\n(task x variant x repetition)"]
    E --> F[Score Responses]
    F --> G[TrialResult list]
    G --> H[Composite Scoring]
    H --> I[Beam Search Cascade]
    I --> J[JSON + CSV Reports]
```

**Key data flow:**

1. **Config** (`EvalRunConfig`) defines repetitions, concurrency, temperature, caching, and output directory.
2. **Tasks** are loaded from YAML via `load_tasks()`, validated against `TaskDefinition`, and dispatched to the correct `EvalTask` subclass.
3. **Variants** are loaded via `load_all()` auto-discovery, each rendering a `DocTree` into an index string.
4. **Trials** are the cross-product of (task, variant, repetition), executed concurrently via `ThreadPoolExecutor`.
5. **Scoring** happens per-trial via `task.score_response()`, then aggregated into per-type means and weighted into a composite score.
6. **Beam search** cascades across axes to identify the best variant configuration.
7. **Reports** are saved as timestamped JSON and CSV files.

---

## 2. Package Structure

The workspace is a UV monorepo with two packages.

```mermaid
graph TB
    subgraph "agent-index"
        AI_SCAN[scanner.py]
        AI_MODELS[models.py<br/>DocTree, DocFile]
        AI_TIERS[tiers.py]
        AI_TRANSFORM[transform.py]
        AI_OUTPUT[output.py]
        AI_CONFIG[config.py]
        AI_CLI[cli.py]

        AI_CLI --> AI_SCAN
        AI_SCAN --> AI_MODELS
        AI_SCAN --> AI_TIERS
        AI_SCAN --> AI_TRANSFORM
        AI_TRANSFORM --> AI_OUTPUT
    end

    subgraph "agent-evals"
        AE_CLI[cli.py]
        AE_RUNNER[runner.py<br/>EvalRunner]
        AE_TASKS[tasks/<br/>11 task types + loader]
        AE_VARIANTS[variants/<br/>40+ variants + registry]
        AE_METRICS[metrics/<br/>6 metrics]
        AE_SCORING[scoring.py<br/>composite, Wilcoxon, bootstrap]
        AE_BEAM[beam_search.py<br/>cascade]
        AE_LLM[llm/<br/>client, cache, token_counter]

        AE_CLI --> AE_RUNNER
        AE_RUNNER --> AE_TASKS
        AE_RUNNER --> AE_VARIANTS
        AE_RUNNER --> AE_LLM
        AE_RUNNER --> AE_METRICS
        AE_BEAM --> AE_RUNNER
        AE_BEAM --> AE_SCORING
    end

    AI_MODELS -.->|DocTree| AE_VARIANTS
    AI_MODELS -.->|DocTree| AE_RUNNER
```

**agent-index** scans a documentation tree, assigns tiers, transforms content, and outputs `.llms.md` index files. Its `DocTree` model is the primary input to agent-evals variants.

**agent-evals** evaluates how well an LLM agent performs when given an index produced by a variant. It contains the task types, variant registry, metrics, LLM client, scoring statistics, and beam search.

---

## 3. Beam Search Cascade

The beam search processes axes in a configured order, scoring all variants per axis and pruning to a fixed beam width. Statistical parity prevents premature elimination.

```mermaid
flowchart TD
    START[Define axis_order and beam_width] --> A1

    subgraph "Per-Axis Loop"
        A1[Axis N: Collect TrialResults] --> A2[score_variants:<br/>group by variant,<br/>compute per-type means,<br/>weighted composite]
        A2 --> A3[Sort candidates<br/>by composite descending]
        A3 --> A4{Candidates ><br/>beam_width?}
        A4 -- No --> A5[Retain all]
        A4 -- Yes --> A6[Pairwise Wilcoxon<br/>vs. best candidate]
        A6 --> A7{p > parity_alpha?}
        A7 -- Yes --> A8[Within parity:<br/>retain in beam]
        A7 -- No --> A9[Significantly worse:<br/>prune]
        A8 --> A10[Apply Holm-Bonferroni<br/>correction]
        A9 --> A10
        A5 --> A10
    end

    A10 --> NEXT{More axes?}
    NEXT -- Yes --> A1
    NEXT -- No --> FINAL[Final beam =<br/>last axis retained set]
    FINAL --> REPORT[format_beam_report]
```

**Key parameters:**

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `beam_width` | 3 | Maximum candidates retained per axis |
| `parity_alpha` | 0.10 | Wilcoxon p-value threshold; p > alpha means "cannot distinguish from best" |
| `n_bootstrap` | 1000 | Bootstrap resamples for confidence intervals |
| `weights` | `DEFAULT_WEIGHTS` | Task-type weights for composite scoring |

**Statistical methods used:**

- **Wilcoxon signed-rank test** (`scipy.stats.wilcoxon`) for paired comparisons.
- **Holm-Bonferroni correction** for multiple comparison control.
- **BCa bootstrap** (`scipy.stats.bootstrap`, method="BCa") for confidence intervals.
- **Rank-biserial correlation** as the effect size measure.

---

## 4. Variant and Task Registration Flow

Both variants and tasks use registry patterns for extensibility. Variants use decorator-based auto-discovery; tasks use explicit function-call registration triggered by module import.

```mermaid
sequenceDiagram
    participant App as Application
    participant VReg as variants/registry.py
    participant VPkg as variants/ package
    participant VMod as format_yaml.py (example)
    participant TInit as tasks/__init__.py
    participant TMod as retrieval.py (example)
    participant TBase as tasks/base.py

    Note over App,VReg: Variant Registration (auto-discovery)
    App->>VReg: load_all()
    VReg->>VPkg: pkgutil.iter_modules(variants.__path__)
    VPkg-->>VReg: [module_info, ...]
    loop Each module in package
        VReg->>VMod: importlib.import_module("agent_evals.variants.format_yaml")
        VMod->>VReg: @register_variant triggers register_variant(FormatYaml)
        VReg->>VReg: _registry[FormatYaml] = FormatYaml()
    end
    App->>VReg: get_all_variants()
    VReg-->>App: [FormatYaml(), ...]

    Note over App,TBase: Task Registration (import-triggered)
    App->>TInit: import agent_evals.tasks
    TInit->>TMod: from agent_evals.tasks.retrieval import RetrievalTask
    TMod->>TBase: register_task_type("retrieval", RetrievalTask)
    TBase->>TBase: TASK_TYPES["retrieval"] = RetrievalTask
    Note over TBase: Repeats for all 11 task type modules
    App->>TBase: TASK_TYPES["retrieval"]
    TBase-->>App: RetrievalTask
```

**Variant registration** is fully automatic: placing a file in `agent-evals/src/agent_evals/variants/` and applying `@register_variant` is sufficient. The `load_all()` function walks the package with `pkgutil.iter_modules` and imports every module.

**Task registration** is import-triggered: the `tasks/__init__.py` imports each concrete task module, and each module calls `register_task_type()` at module level, overriding the `GenericTask` default in the `TASK_TYPES` dict. A lazy guard in `loader.py` (`_ensure_registered()`) ensures this happens even when the loader is imported directly.
