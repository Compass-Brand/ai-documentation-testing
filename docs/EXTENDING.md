# Extending the Evaluation Framework

This guide covers the four most common extension points: adding a variant, a task type, a metric, and gold-standard tasks.

## Prerequisites

- Python 3.11+ installed
- UV package manager (`pip install uv`)
- Project cloned and dependencies installed (`uv sync --dev`)
- Familiarity with the project structure (see `docs/ARCHITECTURE.md`)

---

## 1. Adding a variant

Variants live in `agent-evals/src/agent_evals/variants/`. The registry uses auto-discovery via `pkgutil`, so any module in that package that applies `@register_variant` to a class is automatically picked up.

**Reference:** `agent-evals/src/agent_evals/variants/registry.py`

### Steps

1. Create a new file in the variants package (e.g. `agent-evals/src/agent_evals/variants/format_csv.py`).
2. Subclass `IndexVariant` and implement `metadata()` and `render()`.
3. Decorate the class with `@register_variant`.

### Minimal example

```python
# agent-evals/src/agent_evals/variants/format_csv.py
from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class FormatCsv(IndexVariant):
    """Render the documentation index as CSV."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="format-csv",
            axis=3,               # 0 = baseline, 1-10 = format axes
            category="format",
            description="CSV format for tabular index representation.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        lines = ["path,section,tier,tokens"]
        for _key, doc in sorted(doc_tree.files.items()):
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(f"{doc.rel_path},{doc.section},{doc.tier},{tokens}")
        return "\n".join(lines)
```

### Files to modify

None. Auto-discovery via `load_all()` in `registry.py` handles registration when the package is imported. No changes to `__init__.py` are required for discovery, but if you want the class exported for direct import, add it to `agent-evals/src/agent_evals/variants/__init__.py`.

### How to test

```bash
pytest agent-evals/tests/ -k "variant" -v
```

Write a test that calls `load_all()`, then asserts your variant appears in `get_all_variants()` and `get_variants_for_axis(3)`. Verify that `render()` returns valid CSV for a fixture `DocTree`.

---

## 2. Adding a task type

Task types live in `agent-evals/src/agent_evals/tasks/`. The registry uses auto-discovery via `load_all_task_types()` in `base.py` (the same pattern variants use with `pkgutil`). Each module that calls `register_task_type()` at module level is automatically discovered when the package is imported.

**Reference:** `agent-evals/src/agent_evals/tasks/base.py`

### Steps

1. Add the new type name to `VALID_TASK_TYPES` in `base.py`.
2. Create a new module (e.g. `agent-evals/src/agent_evals/tasks/summarization.py`).
3. Subclass `EvalTask`, implement `build_prompt()` and `score_response()`.
4. Call `register_task_type("summarization", SummarizationTask)` at module level.

No `__init__.py` changes needed -- auto-discovery handles it.

### Minimal example

```python
# agent-evals/src/agent_evals/tasks/summarization.py
from __future__ import annotations

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class SummarizationTask(EvalTask):
    """Task type for evaluating documentation summarization."""

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.max_length: int = meta.get("max_length", 200)

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "Summarize the relevant documentation concisely.\n\n"
                    f"{index_content}"
                ),
            },
            {"role": "user", "content": self.definition.question},
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        if not self.expected_answer:
            return 0.0
        if self.expected_answer.lower() in response.lower():
            return 1.0
        return 0.0


register_task_type("summarization", SummarizationTask)
```

### Files to modify

| File | Change |
|------|--------|
| `tasks/base.py` | Add `"summarization"` to `VALID_TASK_TYPES` |

No changes to `__init__.py` required. Auto-discovery via `load_all_task_types()` imports all task modules automatically.

### How to test

```bash
pytest agent-evals/tests/ -k "task" -v
```

Write tests that load a YAML file with `type: summarization`, verify the correct class is instantiated from `TASK_TYPES`, and check `score_response` against known inputs.

---

## 3. Adding a metric

Metrics live in `agent-evals/src/agent_evals/metrics/`. Each metric subclasses `Metric` and implements a `name` property and `compute()` method.

**Reference:** `agent-evals/src/agent_evals/metrics/base.py`

### Steps

1. Create a new module (e.g. `agent-evals/src/agent_evals/metrics/brevity.py`).
2. Subclass `Metric`, implement `name` and `compute()`.
3. Import the new metric in `agent-evals/src/agent_evals/metrics/__init__.py`.

### Minimal example

```python
# agent-evals/src/agent_evals/metrics/brevity.py
from __future__ import annotations

from agent_evals.metrics.base import Metric, MetricContext


class BrevityMetric(Metric):
    """Penalizes verbose responses. Returns 1.0 for short answers, decaying toward 0.0."""

    @property
    def name(self) -> str:
        return "brevity"

    def compute(self, response: str, context: MetricContext) -> float:
        word_count = len(response.split())
        if word_count <= 50:
            return 1.0
        return max(0.0, min(1.0, 50.0 / word_count))
```

### Files to modify

| File | Change |
|------|--------|
| `metrics/__init__.py` | Add `from agent_evals.metrics.brevity import BrevityMetric` and update `__all__` |

### How to test

```bash
pytest agent-evals/tests/ -k "metric" -v
```

Verify that `compute()` returns values in [0.0, 1.0] for edge cases: empty response, short response, very long response. Construct a `MetricContext` with minimal fixture data.

---

## 4. Adding gold standard tasks

Gold-standard tasks are YAML files loaded by `load_task()` / `load_tasks()` from `agent-evals/src/agent_evals/tasks/loader.py`. Each file must conform to the `TaskDefinition` Pydantic model.

**Reference:** `agent-evals/src/agent_evals/tasks/base.py:61` (`TaskDefinition`)

### Required YAML schema

```yaml
task_id: "<type>_<number>"        # e.g. retrieval_042, code_generation_python_001
type: "<valid_task_type>"         # one of the 11 types in VALID_TASK_TYPES
question: "The question text"
domain: "<valid_domain>"          # framework_api | project_repo | skills_workflows
difficulty: "<level>"             # easy | medium | hard | edge
tags:                             # optional list of string tags
  - "tag1"
  - "tag2"
metadata:                         # type-specific fields (see TASK_METADATA.md)
  expected_answer: "..."
```

### Validation rules

- `task_id` must match the regex `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$` (e.g. `retrieval_001`, `multi_hop_042`).
- `type` must be in `VALID_TASK_TYPES`.
- `domain` must be in `VALID_DOMAINS`.
- `difficulty` must be one of `easy`, `medium`, `hard`, `edge`.
- `task_id` values must be unique across all YAML files loaded by `load_tasks()`.

### Example: Retrieval Task

```yaml
task_id: retrieval_050
type: retrieval
question: "Which file documents the authentication middleware?"
domain: framework_api
difficulty: easy
tags:
  - auth
  - middleware
metadata:
  expected_files:
    - "api/auth.md"
    - "middleware/auth-middleware.md"
  evidence_passage: "AuthMiddleware handles JWT token validation"
```

### Files to create

Place YAML files in a task directory. The `load_tasks(directory)` function recursively scans for `.yaml` and `.yml` files.

### Files to modify

None, unless you are adding a task for a new task type (see section 2 above).

### How to test

```bash
pytest agent-evals/tests/ -k "loader" -v
```

Use `load_task(Path("path/to/task.yaml"))` and verify the returned object is the correct `EvalTask` subclass. Check that invalid YAML raises `ValueError` and missing files raise `FileNotFoundError`.

---

## Troubleshooting

**Variant not discovered after adding a new file:**
- Verify the file is in `agent-evals/src/agent_evals/variants/`
- Verify the class has the `@register_variant` decorator
- Run `python -c "from agent_evals.variants.registry import load_all, get_all_variants; load_all(); print([v.metadata().name for v in get_all_variants()])"` to check

**Task type not found after adding a new module:**
- Verify the type name is in `VALID_TASK_TYPES` in `base.py`
- Verify `register_task_type()` is called at module level (not inside a function)
- Verify the file is in `agent-evals/src/agent_evals/tasks/` (not a subdirectory)

**YAML task fails validation:**
- Check `task_id` matches the regex `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`
- Check `type` is in `VALID_TASK_TYPES` and `domain` is in `VALID_DOMAINS`
- Check `difficulty` is one of: `easy`, `medium`, `hard`, `edge`
