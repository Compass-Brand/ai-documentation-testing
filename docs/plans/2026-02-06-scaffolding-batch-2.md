# Scaffolding Batch 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the next three ready stories: baseline variants (2.2), core task types (2.4), and navigation/consistency metrics (2.8).

**Architecture:** Three independent stories that can run in parallel. Story 2.2 adds 4 baseline `IndexVariant` subclasses to `variants/`. Story 2.4 adds 4 `EvalTask` subclasses to `tasks/` with type-specific Pydantic validation, prompt building, and scoring. Story 2.8 adds 2 `Metric` subclasses to `metrics/`.

**Tech Stack:** Python, Pydantic v2, ABC pattern, `@register_variant` decorator, `register_task_type()` function, `Metric` ABC, numpy for similarity.

**Dependency graph:**
```
Story 2.2 (Baselines)   -- depends on 2.1 (done)
Story 2.4 (Core Tasks)  -- depends on 2.3 (done)
Story 2.8 (Metrics)     -- depends on 2.7 (done)
```

All three are independent of each other and can be implemented in parallel.

---

## Story 2.2: Baseline Variants

Four baselines that bracket variant performance: no-index (lower bound), no-docs (index-only), oracle (upper bound), and length-matched random (noise control).

### Task 1: No-Index Baseline

**Files:**
- Create: `agent-evals/src/agent_evals/variants/baselines.py`
- Test: `agent-evals/tests/test_baselines.py`

**Step 1: Write the failing test**

```python
# agent-evals/tests/test_baselines.py
"""Tests for baseline variants."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import clear_registry, get_all_variants, register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@pytest.fixture(autouse=True)
def _clear() -> None:
    clear_registry()


class TestNoIndexBaseline:
    """Tests for NoIndexBaseline variant."""

    def test_renders_empty_string(self) -> None:
        from agent_evals.variants.baselines import NoIndexBaseline
        variant = NoIndexBaseline()
        result = variant.render(None)  # type: ignore[arg-type]
        assert result == ""

    def test_metadata_is_valid(self) -> None:
        from agent_evals.variants.baselines import NoIndexBaseline
        variant = NoIndexBaseline()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "no-index"
        assert meta.axis == 0  # baselines don't belong to a numbered axis
        assert meta.category == "baseline"

    def test_is_registered(self) -> None:
        from agent_evals.variants import baselines  # noqa: F401 — triggers registration
        variants = get_all_variants()
        names = {v.metadata().name for v in variants}
        assert "no-index" in names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest agent-evals/tests/test_baselines.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

```python
# agent-evals/src/agent_evals/variants/baselines.py
"""Baseline variants for bracketing experimental variant performance.

Four baselines:
- NoIndexBaseline: Agent receives no index (lower bound)
- NoDocsBaseline: Agent receives index only, no actual docs
- OracleBaseline: Agent receives pre-selected relevant docs (upper bound)
- LengthMatchedRandomBaseline: Agent receives random docs of same token count
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class NoIndexBaseline(IndexVariant):
    """Lower bound: agent receives no documentation index at all."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="no-index",
            axis=0,
            category="baseline",
            description="No documentation index provided (lower bound)",
        )

    def render(self, doc_tree: DocTree) -> str:
        return ""
```

Note: axis=0 is used for baselines since they don't belong to any eval axis (1-10). The `VariantMetadata` model currently constrains axis to `ge=1, le=10`, so we need to update it to allow 0 for baselines. Change `base.py` line 31 from `axis: int = Field(ge=1, le=10)` to `axis: int = Field(ge=0, le=10)`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest agent-evals/tests/test_baselines.py::TestNoIndexBaseline -v`
Expected: PASS

### Task 2: No-Docs Baseline

**Step 1: Add failing tests to `test_baselines.py`**

```python
class TestNoDocsBaseline:
    """Tests for NoDocsBaseline variant."""

    def test_renders_index_content_only(self) -> None:
        from agent_evals.variants.baselines import NoDocsBaseline
        variant = NoDocsBaseline()
        # When rendered, returns a message indicating docs are not available
        result = variant.render(None)  # type: ignore[arg-type]
        assert "index only" in result.lower() or "no document content" in result.lower()
        assert len(result) > 0

    def test_metadata_is_valid(self) -> None:
        from agent_evals.variants.baselines import NoDocsBaseline
        variant = NoDocsBaseline()
        meta = variant.metadata()
        assert meta.name == "no-docs"
        assert meta.axis == 0
        assert meta.category == "baseline"
```

**Step 2: Implement NoDocsBaseline in `baselines.py`**

```python
@register_variant
class NoDocsBaseline(IndexVariant):
    """Index-only: agent receives file listing but cannot read document content."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="no-docs",
            axis=0,
            category="baseline",
            description="Index file listing only, no document content available",
        )

    def render(self, doc_tree: DocTree) -> str:
        if doc_tree is None:
            return "No document content available. Index only."
        lines = ["# Documentation Index (no document content available)\n"]
        for doc in doc_tree.files:
            lines.append(f"- {doc.path}")
        return "\n".join(lines)
```

Note: This requires checking what `DocTree.files` looks like. Read `agent-index/src/agent_index/models.py` for the `DocTree` model. Adapt the render to use whatever attributes are available (likely `doc.path` or similar).

**Step 3: Run tests, verify pass**

### Task 3: Oracle Baseline

**Step 1: Add failing tests**

```python
class TestOracleBaseline:
    """Tests for OracleBaseline variant."""

    def test_renders_with_relevant_docs(self) -> None:
        from agent_evals.variants.baselines import OracleBaseline
        variant = OracleBaseline()
        result = variant.render(None)  # type: ignore[arg-type]
        # With no doc_tree, returns a placeholder message
        assert isinstance(result, str)

    def test_metadata_is_valid(self) -> None:
        from agent_evals.variants.baselines import OracleBaseline
        variant = OracleBaseline()
        meta = variant.metadata()
        assert meta.name == "oracle"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_set_relevant_docs(self) -> None:
        from agent_evals.variants.baselines import OracleBaseline
        variant = OracleBaseline()
        variant.set_relevant_docs(["# Auth docs\nOAuth2 flow..."])
        result = variant.render(None)  # type: ignore[arg-type]
        assert "OAuth2" in result
```

**Step 2: Implement OracleBaseline**

```python
@register_variant
class OracleBaseline(IndexVariant):
    """Upper bound: agent receives the exact relevant docs pre-selected in context."""

    def __init__(self) -> None:
        self._relevant_docs: list[str] = []

    def set_relevant_docs(self, docs: list[str]) -> None:
        """Set the relevant documents for the current task.
        Called by the runner before each task evaluation."""
        self._relevant_docs = docs

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="oracle",
            axis=0,
            category="baseline",
            description="Pre-selected relevant docs in context (upper bound)",
        )

    def render(self, doc_tree: DocTree) -> str:
        if not self._relevant_docs:
            return "No relevant documents provided."
        return "\n\n---\n\n".join(self._relevant_docs)
```

### Task 4: Length-Matched Random Baseline

**Step 1: Add failing tests**

```python
class TestLengthMatchedRandomBaseline:
    """Tests for LengthMatchedRandomBaseline variant."""

    def test_metadata_is_valid(self) -> None:
        from agent_evals.variants.baselines import LengthMatchedRandomBaseline
        variant = LengthMatchedRandomBaseline()
        meta = variant.metadata()
        assert meta.name == "length-matched-random"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_renders_with_target_tokens(self) -> None:
        from agent_evals.variants.baselines import LengthMatchedRandomBaseline
        variant = LengthMatchedRandomBaseline()
        variant.set_target_tokens(100)
        result = variant.render(None)  # type: ignore[arg-type]
        assert isinstance(result, str)

    def test_renders_empty_without_doc_tree(self) -> None:
        from agent_evals.variants.baselines import LengthMatchedRandomBaseline
        variant = LengthMatchedRandomBaseline()
        result = variant.render(None)  # type: ignore[arg-type]
        assert isinstance(result, str)
```

**Step 2: Implement LengthMatchedRandomBaseline**

```python
import random

@register_variant
class LengthMatchedRandomBaseline(IndexVariant):
    """Noise control: agent receives random docs of the same total token count.

    Controls for the "more tokens = better" confound.
    """

    def __init__(self) -> None:
        self._target_tokens: int = 0
        self._rng = random.Random(42)

    def set_target_tokens(self, tokens: int) -> None:
        """Set the target token count to match."""
        self._target_tokens = tokens

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="length-matched-random",
            axis=0,
            category="baseline",
            description="Random docs matching target variant's token count",
        )

    def render(self, doc_tree: DocTree) -> str:
        if doc_tree is None or not hasattr(doc_tree, "files") or not doc_tree.files:
            return ""
        # Shuffle docs and take until we reach target token estimate
        docs = list(doc_tree.files)
        self._rng.shuffle(docs)
        lines: list[str] = []
        token_est = 0
        for doc in docs:
            content = getattr(doc, "content", "") or str(doc.path)
            est = len(content) // 4
            if token_est + est > self._target_tokens and lines:
                break
            lines.append(content)
            token_est += est
        return "\n\n---\n\n".join(lines)
```

**Step 5: Commit Story 2.2**

```bash
git add agent-evals/src/agent_evals/variants/baselines.py \
       agent-evals/src/agent_evals/variants/base.py \
       agent-evals/tests/test_baselines.py
git commit -m "feat(agent-evals): Add baseline variants (no-index, no-docs, oracle, length-matched-random)"
```

---

## Story 2.4: Task Types — Core (Types 1-4)

Four highest-weight task type implementations: retrieval (0.15), fact_extraction (0.15), code_generation (0.15), agentic (0.12). Combined weight: 0.57.

Each task type extends `EvalTask` with type-specific Pydantic fields, prompt construction, and scoring.

### Task 5: Retrieval Task Type

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/retrieval.py`
- Test: `agent-evals/tests/test_task_retrieval.py`

**Key Requirements:**
- Additional YAML fields: `expected_files: list[str]`, `evidence_passage: str`
- Primary metric: F-beta (beta=2) — recall-weighted
- Secondary: Recall@K, MRR
- `score_response()` extracts file paths from response, computes F-beta against expected_files

**Step 1: Write failing test**

```python
"""Tests for retrieval task type."""
from __future__ import annotations

import pytest
from agent_evals.tasks.base import TaskDefinition


class TestRetrievalTaskDefinition:
    """Tests for retrieval-specific TaskDefinition fields."""

    def test_valid_retrieval_task(self) -> None:
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_001",
            type="retrieval",
            question="Which file documents OAuth2?",
            domain="framework_api",
            difficulty="easy",
            metadata={
                "expected_files": ["docs/api/auth.md"],
                "evidence_passage": "OAuth2 flow is documented in...",
            },
        )
        task = RetrievalTask(defn)
        assert task.expected_files == ["docs/api/auth.md"]

    def test_build_prompt_includes_question(self) -> None:
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_002",
            type="retrieval",
            question="Where is the auth config?",
            domain="framework_api",
            difficulty="easy",
            metadata={"expected_files": ["config/auth.yaml"]},
        )
        task = RetrievalTask(defn)
        messages = task.build_prompt("# Index\n- config/auth.yaml\n- src/main.py")
        all_content = " ".join(m["content"] for m in messages)
        assert "auth config" in all_content.lower()

    def test_score_response_perfect_match(self) -> None:
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_003",
            type="retrieval",
            question="Which file?",
            domain="framework_api",
            difficulty="easy",
            metadata={"expected_files": ["docs/auth.md"]},
        )
        task = RetrievalTask(defn)
        score = task.score_response("The auth flow is in docs/auth.md")
        assert score == pytest.approx(1.0)

    def test_score_response_no_match(self) -> None:
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_004",
            type="retrieval",
            question="Which file?",
            domain="framework_api",
            difficulty="easy",
            metadata={"expected_files": ["docs/auth.md"]},
        )
        task = RetrievalTask(defn)
        score = task.score_response("I don't know which file that is.")
        assert score == pytest.approx(0.0)

    def test_score_response_partial_match(self) -> None:
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_005",
            type="retrieval",
            question="Which files handle auth?",
            domain="framework_api",
            difficulty="medium",
            metadata={"expected_files": ["docs/auth.md", "docs/oauth.md"]},
        )
        task = RetrievalTask(defn)
        # Only mentions one of two expected files
        score = task.score_response("Check docs/auth.md for auth details.")
        assert 0.0 < score < 1.0

    def test_fbeta_favors_recall(self) -> None:
        """F-beta with beta=2 should favor recall over precision."""
        from agent_evals.tasks.retrieval import RetrievalTask
        defn = TaskDefinition(
            task_id="retrieval_006",
            type="retrieval",
            question="Which files?",
            domain="framework_api",
            difficulty="medium",
            metadata={"expected_files": ["a.md", "b.md"]},
        )
        task = RetrievalTask(defn)
        # Response mentions both expected + one extra (high recall, lower precision)
        score_high_recall = task.score_response("Check a.md, b.md, and also c.md")
        # Response mentions one expected only (low recall, high precision)
        score_high_precision = task.score_response("Check a.md")
        assert score_high_recall > score_high_precision
```

**Step 2: Implement RetrievalTask**

```python
# agent-evals/src/agent_evals/tasks/retrieval.py
"""Retrieval task type: 'Which file answers this question?'

Primary metric: F-beta (beta=2), weighting recall over precision.
"""
from __future__ import annotations

import re
from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class RetrievalTask(EvalTask):
    """Retrieval task: identifies which files answer a question.

    Scores using F-beta (beta=2) comparing extracted file paths
    in the response against expected_files.
    """

    BETA: float = 2.0

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_files: list[str] = meta.get("expected_files", [])
        self.evidence_passage: str = meta.get("evidence_passage", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a documentation assistant. Given the following "
                    "documentation index, identify which file(s) answer the "
                    "user's question. List file paths explicitly.\n\n"
                    f"{index_content}"
                ),
            },
            {"role": "user", "content": self.definition.question},
        ]

    def score_response(self, response: str, **kwargs: Any) -> float:
        """Score using F-beta (beta=2) on file path matching."""
        extracted = self._extract_file_paths(response)
        if not self.expected_files:
            return 1.0 if not extracted else 0.0

        expected_set = {f.lower().strip() for f in self.expected_files}
        extracted_set = {f.lower().strip() for f in extracted}

        true_positives = len(expected_set & extracted_set)
        precision = true_positives / len(extracted_set) if extracted_set else 0.0
        recall = true_positives / len(expected_set) if expected_set else 0.0

        if precision + recall == 0:
            return 0.0

        beta_sq = self.BETA ** 2
        fbeta = (1 + beta_sq) * (precision * recall) / (beta_sq * precision + recall)
        return fbeta

    @staticmethod
    def _extract_file_paths(text: str) -> list[str]:
        """Extract file paths from response text."""
        # Match common file path patterns
        pattern = r'(?:^|\s|`|"|\'|\()([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)'
        matches = re.findall(pattern, text)
        # Filter to likely file paths (must contain / or \ or end with common extensions)
        file_exts = {".md", ".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".rst", ".html"}
        return [m for m in matches if any(m.lower().endswith(ext) for ext in file_exts)]


register_task_type("retrieval", RetrievalTask)
```

**Step 3: Run tests, verify pass**

Run: `uv run pytest agent-evals/tests/test_task_retrieval.py -v`

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/retrieval.py agent-evals/tests/test_task_retrieval.py
git commit -m "feat(agent-evals): Add retrieval task type with F-beta scoring"
```

### Task 6: Fact Extraction Task Type

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/fact_extraction.py`
- Test: `agent-evals/tests/test_task_fact_extraction.py`

**Key Requirements:**
- Additional YAML fields: `expected_answer: str`, `answer_aliases: list[str]`, `source_location: str`, `fact_type: str`
- Primary: LLM-as-judge (deferred to runner integration; stub with keyword matching)
- Secondary: keyword matching with aliases
- `score_response()` checks expected_answer + aliases against response

**Implementation approach:** For now, implement the deterministic keyword-matching scorer. The LLM-as-judge scorer will be wired in when the runner (Story 2.13) provides judge model access. The task class should have a `score_response()` that works standalone.

```python
# agent-evals/src/agent_evals/tasks/fact_extraction.py
class FactExtractionTask(EvalTask):
    """Fact extraction: 'What does this API do?'

    Scores by checking if expected_answer or any alias appears in the response.
    Normalized to 0-1 by matching keywords from expected answer.
    """
    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self.source_location: str = meta.get("source_location", "")
        self.fact_type: str = meta.get("fact_type", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a documentation assistant. Answer the user's "
                    "question using the documentation index below. Be factual "
                    "and precise.\n\n"
                    f"{index_content}"
                ),
            },
            {"role": "user", "content": self.definition.question},
        ]

    def score_response(self, response: str, **kwargs: Any) -> float:
        """Score using keyword matching against expected answer and aliases."""
        response_lower = response.lower()
        all_answers = [self.expected_answer] + self.answer_aliases
        all_answers = [a for a in all_answers if a]  # filter empty

        if not all_answers:
            return 0.0

        # Check if any complete answer/alias appears in response
        for answer in all_answers:
            if answer.lower() in response_lower:
                return 1.0

        # Partial matching: what fraction of expected answer keywords appear?
        keywords = self._extract_keywords(self.expected_answer)
        if not keywords:
            return 0.0
        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return matched / len(keywords)

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords (3+ chars, not stopwords)."""
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on",
                     "at", "to", "for", "of", "with", "and", "or", "not", "it",
                     "this", "that", "from", "by", "as", "be", "has", "have"}
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        return [w for w in words if w.lower() not in stopwords]

register_task_type("fact_extraction", FactExtractionTask)
```

**Tests:** Mirror retrieval test structure — perfect match, no match, partial match, alias matching.

### Task 7: Code Generation Task Type

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/code_generation.py`
- Test: `agent-evals/tests/test_task_code_generation.py`

**Key Requirements:**
- Additional YAML fields: `expected_answer: str`, `test: str`, `entry_point: str`, `canonical_solution: str`, `libs: list[str]`, `doc_struct: dict`
- Primary: deterministic test suite (regex patterns + forbidden anti-patterns)
- `score_response()` checks: (1) regex patterns from `test` field, (2) forbidden patterns
- Does NOT execute code (security) — uses pattern matching only

```python
# agent-evals/src/agent_evals/tasks/code_generation.py
class CodeGenerationTask(EvalTask):
    """Code generation: 'Write code using this API.'

    Scores using regex pattern matching against expected patterns
    and anti-patterns. Does not execute code.
    """
    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.test_patterns: str = meta.get("test", "")
        self.entry_point: str = meta.get("entry_point", "")
        self.canonical_solution: str = meta.get("canonical_solution", "")
        self.libs: list[str] = meta.get("libs", [])
        self.doc_struct: dict[str, Any] = meta.get("doc_struct", {})
        self.forbidden_patterns: list[str] = meta.get("forbidden_patterns", [])

    def score_response(self, response: str, **kwargs: Any) -> float:
        """Score by checking required patterns and forbidden anti-patterns."""
        if not self.test_patterns and not self.forbidden_patterns:
            return 0.0

        required = self._parse_patterns(self.test_patterns)
        forbidden = self.forbidden_patterns

        # Check required patterns
        required_score = 0.0
        if required:
            matched = sum(1 for p in required if re.search(p, response, re.DOTALL))
            required_score = matched / len(required)

        # Check forbidden patterns (penalty)
        forbidden_penalty = 0.0
        if forbidden:
            violations = sum(1 for p in forbidden if re.search(p, response, re.DOTALL))
            forbidden_penalty = violations / len(forbidden)

        # Combine: required patterns weighted 0.8, forbidden penalty weighted 0.2
        score = required_score * 0.8 + (1.0 - forbidden_penalty) * 0.2
        return max(0.0, min(1.0, score))

    @staticmethod
    def _parse_patterns(test_field: str) -> list[str]:
        """Parse test field into regex patterns (one per line)."""
        if not test_field:
            return []
        return [line.strip() for line in test_field.strip().splitlines() if line.strip()]

register_task_type("code_generation", CodeGenerationTask)
```

### Task 8: End-to-End Agentic Task Type

**Files:**
- Create: `agent-evals/src/agent_evals/tasks/agentic.py`
- Test: `agent-evals/tests/test_task_agentic.py`

**Key Requirements:**
- Additional YAML fields: `expected_tools: list[dict]`, `files: dict`, `setup_script: str`, `FAIL_TO_PASS: str` (JSON), `PASS_TO_PASS: str` (JSON), `message_limit: int`, `token_limit: int`
- Composite scoring: retrieval invocation + file selection + output correctness
- `FAIL_TO_PASS` and `PASS_TO_PASS` stored as JSON strings — use `json.loads()` to parse
- For scaffolding: implement scoring of tool call presence and file selection accuracy

```python
# agent-evals/src/agent_evals/tasks/agentic.py
import json

class AgenticTask(EvalTask):
    """End-to-end agentic task with tool-call access to the index.

    Composite scoring: retrieval invocation, file selection, output correctness.
    """
    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_tools: list[dict[str, Any]] = meta.get("expected_tools", [])
        self.files: dict[str, Any] = meta.get("files", {})
        self.setup_script: str = meta.get("setup_script", "")
        self.message_limit: int = int(meta.get("message_limit", 20))
        self.token_limit: int = int(meta.get("token_limit", 0))

        # Parse JSON strings for SWE-bench format
        fail_to_pass_raw = meta.get("FAIL_TO_PASS", "[]")
        pass_to_pass_raw = meta.get("PASS_TO_PASS", "[]")
        self.fail_to_pass: list[str] = (
            json.loads(fail_to_pass_raw) if isinstance(fail_to_pass_raw, str)
            else fail_to_pass_raw
        )
        self.pass_to_pass: list[str] = (
            json.loads(pass_to_pass_raw) if isinstance(pass_to_pass_raw, str)
            else pass_to_pass_raw
        )

    def score_response(self, response: str, **kwargs: Any) -> float:
        """Composite score: tool invocation (0.3) + file selection (0.3) + correctness (0.4)."""
        tool_calls: list[dict[str, Any]] = kwargs.get("tool_calls", [])  # type: ignore[assignment]

        tool_score = self._score_tool_invocation(tool_calls)
        file_score = self._score_file_selection(tool_calls)
        correctness_score = self._score_correctness(response)

        return tool_score * 0.3 + file_score * 0.3 + correctness_score * 0.4

    def _score_tool_invocation(self, tool_calls: list[dict[str, Any]]) -> float:
        """Did the agent invoke the expected tools?"""
        if not self.expected_tools:
            return 1.0 if tool_calls else 0.0
        expected_names = {t.get("name", "") for t in self.expected_tools}
        actual_names = {t.get("name", "") for t in tool_calls}
        if not expected_names:
            return 1.0
        matched = len(expected_names & actual_names)
        return matched / len(expected_names)

    def _score_file_selection(self, tool_calls: list[dict[str, Any]]) -> float:
        """Did the agent read the right files?"""
        if not self.files:
            return 1.0
        expected_files = set(self.files.keys())
        accessed_files: set[str] = set()
        for call in tool_calls:
            args = call.get("arguments", {})
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str) and ("/" in v or "\\" in v or "." in v):
                        accessed_files.add(v)
        if not expected_files:
            return 1.0
        matched = len(expected_files & accessed_files)
        return matched / len(expected_files)

    def _score_correctness(self, response: str) -> float:
        """Basic correctness: check if FAIL_TO_PASS test names appear resolved."""
        if not self.fail_to_pass:
            return 0.0 if not response.strip() else 0.5
        # Heuristic: check if test identifiers are mentioned in response
        mentioned = sum(1 for t in self.fail_to_pass if t in response)
        return mentioned / len(self.fail_to_pass) if self.fail_to_pass else 0.0

register_task_type("agentic", AgenticTask)
```

**Step 5: Commit Story 2.4**

```bash
git add agent-evals/src/agent_evals/tasks/retrieval.py \
       agent-evals/src/agent_evals/tasks/fact_extraction.py \
       agent-evals/src/agent_evals/tasks/code_generation.py \
       agent-evals/src/agent_evals/tasks/agentic.py \
       agent-evals/tests/test_task_retrieval.py \
       agent-evals/tests/test_task_fact_extraction.py \
       agent-evals/tests/test_task_code_generation.py \
       agent-evals/tests/test_task_agentic.py
git commit -m "feat(agent-evals): Add core task types (retrieval, fact_extraction, code_generation, agentic)"
```

---

## Story 2.8: Metrics — Navigation & Consistency

Two cross-cutting metrics: navigation path quality (for agentic tasks) and response consistency (across repetitions).

### Task 9: Navigation Path Quality Metric

**Files:**
- Create: `agent-evals/src/agent_evals/metrics/navigation.py`
- Test: `agent-evals/tests/test_metrics_navigation.py`

**Key Requirements:**
- Measures actual vs optimal file-read sequence from tool calls
- Penalizes backtracking (re-reading same files)
- Penalizes unnecessary reads (files not relevant to task)
- Returns 0.0-1.0 where 1.0 = optimal path

```python
# agent-evals/src/agent_evals/metrics/navigation.py
"""Navigation path quality metric for agentic tasks.

Compares actual file-read sequence against optimal path.
Penalizes backtracking and unnecessary reads.
"""
from __future__ import annotations

from typing import Any

from agent_evals.metrics.base import Metric, MetricContext


class NavigationPathMetric(Metric):
    """Measures efficiency of file navigation in agentic tasks.

    Score components:
    - Relevance: fraction of reads that hit relevant files
    - Efficiency: optimal reads / actual reads (penalizes extra reads)
    - Ordering: penalizes backtracking (reading a file then re-reading it later)
    """

    @property
    def name(self) -> str:
        return "navigation_path_quality"

    def compute(self, response: str, context: MetricContext) -> float:
        tool_calls = context.tool_calls or []
        if not tool_calls:
            return 0.0

        reads = self._extract_file_reads(tool_calls)
        if not reads:
            return 0.0

        # Determine relevant files from task metadata
        task_meta = context.task_definition
        relevant_files: set[str] = set()
        if isinstance(task_meta, dict):
            for key in ("expected_files", "files"):
                val = task_meta.get(key, [])
                if isinstance(val, list):
                    relevant_files.update(str(v) for v in val)
                elif isinstance(val, dict):
                    relevant_files.update(val.keys())

        if not relevant_files:
            return 1.0  # No ground truth, can't penalize

        # Relevance: fraction of reads targeting relevant files
        relevant_reads = sum(1 for r in reads if r in relevant_files)
        relevance = relevant_reads / len(reads)

        # Efficiency: optimal count / actual count
        optimal_count = len(relevant_files)
        efficiency = min(optimal_count / len(reads), 1.0)

        # Backtracking penalty: count re-reads
        unique_reads = len(set(reads))
        backtrack_penalty = 1.0 - (len(reads) - unique_reads) / max(len(reads), 1)

        return (relevance * 0.4 + efficiency * 0.3 + backtrack_penalty * 0.3)

    @staticmethod
    def _extract_file_reads(tool_calls: list[dict[str, Any]]) -> list[str]:
        """Extract file paths from tool call arguments."""
        reads: list[str] = []
        for call in tool_calls:
            name = call.get("name", "")
            if "read" in name.lower() or "open" in name.lower() or "file" in name.lower():
                args = call.get("arguments", {})
                if isinstance(args, dict):
                    for v in args.values():
                        if isinstance(v, str) and ("/" in v or "." in v):
                            reads.append(v)
        return reads
```

### Task 10: Consistency Metric

**Files:**
- Create: `agent-evals/src/agent_evals/metrics/consistency.py`
- Test: `agent-evals/tests/test_metrics_consistency.py`

**Key Requirements:**
- Computes pairwise similarity across N repetitions of the same task
- Uses token overlap (Jaccard similarity) as the default similarity measure
- High variance = weak index format
- Returns mean pairwise similarity (0.0-1.0)

```python
# agent-evals/src/agent_evals/metrics/consistency.py
"""Consistency metric: pairwise similarity across repetitions.

High consistency = stable index format. Low consistency = brittle.
"""
from __future__ import annotations

import re

from agent_evals.metrics.base import Metric, MetricContext


class ConsistencyMetric(Metric):
    """Measures response consistency across repetitions.

    Computes mean pairwise Jaccard similarity of token sets.
    Designed to be called with prior_responses passed via context
    or kwargs.
    """

    @property
    def name(self) -> str:
        return "consistency"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute consistency against prior responses.

        Expects context.task_definition["prior_responses"] to be a list
        of previous response strings for the same task/variant.
        """
        prior: list[str] = []
        if isinstance(context.task_definition, dict):
            prior = context.task_definition.get("prior_responses", [])

        if not prior:
            return 1.0  # First response, no comparison possible

        current_tokens = self._tokenize(response)
        similarities: list[float] = []
        for prev in prior:
            prev_tokens = self._tokenize(prev)
            sim = self._jaccard(current_tokens, prev_tokens)
            similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 1.0

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Simple whitespace + punctuation tokenizer."""
        return set(re.findall(r'\b\w+\b', text.lower()))

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        """Jaccard similarity between two token sets."""
        if not a and not b:
            return 1.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union > 0 else 0.0
```

**Step 5: Update metrics `__init__.py` and commit**

Add `NavigationPathMetric` and `ConsistencyMetric` to `agent-evals/src/agent_evals/metrics/__init__.py`.

```bash
git add agent-evals/src/agent_evals/metrics/navigation.py \
       agent-evals/src/agent_evals/metrics/consistency.py \
       agent-evals/src/agent_evals/metrics/__init__.py \
       agent-evals/tests/test_metrics_navigation.py \
       agent-evals/tests/test_metrics_consistency.py
git commit -m "feat(agent-evals): Add navigation path and consistency metrics"
```

---

## Verification

After all three stories:

```bash
uv run pytest --tb=short -q                  # All tests pass
uv run ruff check agent-evals/               # Clean
uv run mypy --strict agent-evals/src/ agent-evals/tests/  # Clean
```

## Summary

| Task | Story | Component | Estimated Tests |
|------|-------|-----------|-----------------|
| 1-4 | 2.2 | 4 baseline variants | ~15 tests |
| 5 | 2.4 | RetrievalTask | ~8 tests |
| 6 | 2.4 | FactExtractionTask | ~8 tests |
| 7 | 2.4 | CodeGenerationTask | ~8 tests |
| 8 | 2.4 | AgenticTask | ~8 tests |
| 9 | 2.8 | NavigationPathMetric | ~6 tests |
| 10 | 2.8 | ConsistencyMetric | ~6 tests |

**Total: ~59 new tests across 10 tasks in 3 stories.**

## Important Implementation Notes

1. **axis=0 for baselines**: The `VariantMetadata` model needs `axis: int = Field(ge=0, le=10)` (change ge=1 to ge=0) to allow baselines on axis 0.

2. **Task type registration**: Each task module must call `register_task_type()` at module level to override the `GenericTask` default. The import must happen before tasks are loaded.

3. **DocTree interface**: Story 2.2 (baselines) needs to know the `DocTree` model structure. Check `agent-index/src/agent_index/models.py` for `DocTree.files` and `DocFile` attributes before implementing `NoDocsBaseline` and `LengthMatchedRandomBaseline`.

4. **No code execution**: `CodeGenerationTask.score_response()` uses regex pattern matching only — never executes user-provided code.

5. **JSON parsing for agentic tasks**: SWE-bench stores `FAIL_TO_PASS` and `PASS_TO_PASS` as JSON strings. Always use `json.loads()` to parse them.
