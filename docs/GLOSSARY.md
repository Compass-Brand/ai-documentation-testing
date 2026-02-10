# Glossary

Key terms used throughout the agent-evals and agent-index codebase.

| Term | Definition | Code Reference |
|------|-----------|---------------|
| **Axis** | A numbered evaluation dimension (0--10). Axis 0 holds baseline variants (no-index, no-docs, oracle, length-matched-random); axes 1--10 each isolate one format property (structure, scale, format, metadata, etc.). | `agent-evals/src/agent_evals/variants/base.py:24` (`VariantMetadata.axis`) |
| **Beam Search** | A cascade algorithm that evaluates variants axis-by-axis, retaining a fixed-width set of top candidates at each stage and using Wilcoxon tests to avoid premature elimination. | `agent-evals/src/agent_evals/beam_search.py:200` (`run_beam_cascade`) |
| **Canary / Sentinel Task** | A negative (unanswerable) task included in every run to verify the agent abstains rather than hallucinating; acts as a quality-control check. | `agent-evals/src/agent_evals/tasks/negative.py:69` (`NegativeTask`) |
| **Composite Score** | A weighted sum of per-task-type mean scores mapped to a 0--100 scale; weights are defined per scheme and must sum to 1.0. | `agent-evals/src/agent_evals/scoring.py:91` (`composite_score`) |
| **Domain** | The subject area a gold-standard task belongs to: `framework_api`, `project_repo`, or `skills_workflows`. | `agent-evals/src/agent_evals/tasks/base.py:37` (`VALID_DOMAINS`) |
| **Gold Standard** | A hand-authored YAML task definition containing a question, expected answer, metadata, and scoring inputs used as ground truth during evaluation. | `agent-evals/src/agent_evals/tasks/base.py:61` (`TaskDefinition`) |
| **Metric** | An independent quality signal (faithfulness, abstention, consistency, etc.) computed from a response and its `MetricContext`, always returning a value in [0.0, 1.0]. | `agent-evals/src/agent_evals/metrics/base.py:31` (`Metric`) |
| **Repetition** | A 1-based counter for how many times the same (task, variant) pair is evaluated in a single run; multiple repetitions capture LLM variance. | `agent-evals/src/agent_evals/runner.py:65` (`TrialResult.repetition`) |
| **Task** | A single evaluation item defined in YAML and loaded as an `EvalTask` instance; contains a question, expected outputs, and type-specific metadata consumed by the scorer. | `agent-evals/src/agent_evals/tasks/base.py:123` (`EvalTask`) |
| **Task Type** | One of 11 categories (retrieval, fact_extraction, code_generation, agentic, multi_hop, negative, compositional, robustness, disambiguation, conflicting, efficiency) that determines how a task is prompted and scored. | `agent-evals/src/agent_evals/tasks/base.py:23` (`VALID_TASK_TYPES`) |
| **Tier** | A priority label assigned to a documentation file during indexing (e.g. `required`, `optional`); used by structure variants to control inclusion and ordering. | `agent-evals/src/agent_evals/variants/baselines.py:85` (used in `NoDocsBaseline.render`) |
| **Trial** | A single execution of one (task, variant, repetition) triple, producing a `TrialResult` with score, token counts, latency, and cost. | `agent-evals/src/agent_evals/runner.py:43` (`TrialResult`) |
| **Variant** | A concrete `IndexVariant` subclass that renders a `DocTree` into a specific index format; registered via `@register_variant` and identified by axis and name. | `agent-evals/src/agent_evals/variants/base.py:37` (`IndexVariant`) |
