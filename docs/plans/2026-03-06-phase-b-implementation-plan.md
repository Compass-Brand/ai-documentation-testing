# Phase B Implementation Plan: Operational Metrics

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Every trial captures Cost, Latency, Stability, and Security metrics from OpenRouter, enabling cost-efficiency Pareto frontiers and multi-objective Taguchi analysis.

**Architecture:** Extend the existing `GenerationResult` and `TrialResult` to capture OpenRouter's full usage metadata (cached_tokens, reasoning_tokens, provider, cache_discount). Add a post-hoc generation stats fetcher. Extend reporting with stability metrics and cost-efficiency tables. Enable Taguchi analysis on cost/latency as alternative response variables.

**Tech Stack:** Python 3.11+, UV workspace, pytest, LiteLLM (OpenRouter), httpx (generation stats API)

**Key insight from exploration:** Most raw operational data is already captured. `GenerationResult` has cost, api_call_ms, retry_count, generation_id. `TrialResult` has latency_seconds, cost, and a metrics dict. What's missing: cached_tokens, reasoning_tokens, provider name, cache_discount, and the aggregation/reporting layer.

**Guardrails:** Same as Phase A — TDD, 80%+ coverage, all tests pass before commit, type hints, max 300 lines/file, max 50 lines/function.

**Commands:**
- Run all tests: `~/.local/bin/uv run pytest agent-evals/tests/ -v`
- Run with coverage: `~/.local/bin/uv run pytest agent-evals/tests/ --cov=agent_evals --cov-report=term-missing`

---

## Task 0: Verify Phase A Baseline

**Step 1: Confirm all Phase A tests pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
```

Record test count. Phase B must only add tests, never break existing ones.

---

## Task 1: Extend GenerationResult with OpenRouter Metadata

**Purpose:** Capture cached_tokens, cache_write_tokens, reasoning_tokens, and provider from OpenRouter responses that LiteLLM passes through.

**Files:**
- Modify: `agent-evals/src/agent_evals/llm/client.py` (lines 28-42 GenerationResult, lines 199-235 metadata extraction)
- Modify: `agent-evals/tests/test_llm_client.py`

### Step 1: Write failing tests

**Append to:** `agent-evals/tests/test_llm_client.py`

```python
class TestGenerationResultExtendedMetadata:
    def test_cached_tokens_field_exists(self):
        from agent_evals.llm.client import GenerationResult

        result = GenerationResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01,
            model="test-model",
            generation_id="gen-123",
            cached_tokens=80,
        )
        assert result.cached_tokens == 80

    def test_cached_tokens_defaults_to_zero(self):
        from agent_evals.llm.client import GenerationResult

        result = GenerationResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=None,
            model="test-model",
            generation_id=None,
        )
        assert result.cached_tokens == 0

    def test_reasoning_tokens_field_exists(self):
        from agent_evals.llm.client import GenerationResult

        result = GenerationResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=None,
            model="test-model",
            generation_id=None,
            reasoning_tokens=20,
        )
        assert result.reasoning_tokens == 20

    def test_cache_write_tokens_field_exists(self):
        from agent_evals.llm.client import GenerationResult

        result = GenerationResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=None,
            model="test-model",
            generation_id=None,
            cache_write_tokens=100,
        )
        assert result.cache_write_tokens == 100

    def test_provider_field_exists(self):
        from agent_evals.llm.client import GenerationResult

        result = GenerationResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=None,
            model="test-model",
            generation_id=None,
            provider="Anthropic",
        )
        assert result.provider == "Anthropic"
```

### Step 2: Run tests to verify failure

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_llm_client.py::TestGenerationResultExtendedMetadata -v
```

Expected: TypeError — unexpected keyword argument.

### Step 3: Add fields to GenerationResult

**Modify:** `agent-evals/src/agent_evals/llm/client.py` (lines 28-42)

Add after existing fields:

```python
cached_tokens: int = 0
cache_write_tokens: int = 0
reasoning_tokens: int = 0
provider: str | None = None
```

### Step 4: Extract metadata from LiteLLM response

**Modify:** `agent-evals/src/agent_evals/llm/client.py` in `complete()` method, after existing metadata extraction (around line 225-235).

```python
# Extract extended OpenRouter metadata
usage = getattr(response, "usage", None)
cached_tokens = 0
cache_write_tokens = 0
reasoning_tokens = 0

if usage:
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details:
        cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
        cache_write_tokens = getattr(prompt_details, "cache_write_tokens", 0) or 0

    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details:
        reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0

# Extract provider from response (OpenRouter includes this)
provider = getattr(response, "provider", None)
```

Then include in the GenerationResult constructor call:

```python
cached_tokens=cached_tokens,
cache_write_tokens=cache_write_tokens,
reasoning_tokens=reasoning_tokens,
provider=provider,
```

### Step 5: Write test for metadata extraction from mock LiteLLM response

```python
class TestExtendedMetadataExtraction:
    def test_extracts_cached_tokens_from_response(self):
        """LLMClient extracts prompt_tokens_details.cached_tokens."""
        from unittest.mock import MagicMock, patch

        from agent_evals.llm.client import LLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.id = "gen-test"
        mock_response.model = "test-model"
        mock_response.provider = "Anthropic"

        # Set up usage with details
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_response.usage.prompt_tokens_details.cached_tokens = 80
        mock_response.usage.prompt_tokens_details.cache_write_tokens = 20
        mock_response.usage.completion_tokens_details.reasoning_tokens = 10

        mock_response._hidden_params = {"response_cost": 0.005}

        with patch("agent_evals.llm.client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response
            client = LLMClient(model="test", api_key="fake")
            result = client.complete([{"role": "user", "content": "hi"}])

            assert result.cached_tokens == 80
            assert result.cache_write_tokens == 20
            assert result.reasoning_tokens == 10
            assert result.provider == "Anthropic"

    def test_handles_missing_token_details_gracefully(self):
        """When prompt_tokens_details is None, defaults to 0."""
        from unittest.mock import MagicMock, patch

        from agent_evals.llm.client import LLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.choices[0].message.tool_calls = None
        mock_response.id = "gen-test"
        mock_response.model = "test-model"
        mock_response.provider = None
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response._hidden_params = {"response_cost": 0.001}

        with patch("agent_evals.llm.client.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response
            client = LLMClient(model="test", api_key="fake")
            result = client.complete([{"role": "user", "content": "hi"}])

            assert result.cached_tokens == 0
            assert result.cache_write_tokens == 0
            assert result.reasoning_tokens == 0
```

### Step 6: Run tests, verify all pass

### Step 7: Run full test suite (no regressions)

### Step 8: Commit

```bash
git commit -m "feat(llm): capture cached_tokens, reasoning_tokens, provider from OpenRouter"
```

---

## Task 2: Generation Stats Fetcher

**Purpose:** Call OpenRouter's `/api/v1/generation?id=gen-XXX` endpoint after each trial to get latency, cache_discount, and provider_responses.

**Files:**
- Create: `agent-evals/src/agent_evals/llm/generation_stats.py`
- Create: `agent-evals/tests/test_generation_stats.py`

### Step 1: Write failing tests

**File:** `agent-evals/tests/test_generation_stats.py`

```python
"""Tests for OpenRouter generation stats fetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_evals.llm.generation_stats import GenerationStats, fetch_generation_stats


class TestGenerationStats:
    def test_dataclass_fields(self):
        stats = GenerationStats(
            generation_id="gen-123",
            latency_ms=450.0,
            generation_time_ms=380.0,
            cache_discount=0.003,
            provider_name="Anthropic",
            provider_fallbacks=0,
            native_tokens_cached=80,
            native_tokens_reasoning=10,
            streamed=False,
        )
        assert stats.latency_ms == 450.0
        assert stats.provider_name == "Anthropic"
        assert stats.provider_fallbacks == 0

    def test_provider_fallbacks_counted(self):
        stats = GenerationStats(
            generation_id="gen-123",
            latency_ms=900.0,
            generation_time_ms=400.0,
            cache_discount=None,
            provider_name="Google",
            provider_fallbacks=2,
            native_tokens_cached=0,
            native_tokens_reasoning=0,
            streamed=False,
        )
        assert stats.provider_fallbacks == 2


class TestFetchGenerationStats:
    def test_returns_stats_on_success(self):
        mock_response_data = {
            "data": {
                "id": "gen-123",
                "latency": 450,
                "generation_time": 380,
                "cache_discount": 0.003,
                "provider_name": "Anthropic",
                "provider_responses": [
                    {"status": 200, "latency": 380},
                ],
                "native_tokens_cached": 80,
                "native_tokens_reasoning": 10,
                "streamed": False,
            }
        }

        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response_data
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-123", api_key="fake-key")
            assert stats is not None
            assert stats.latency_ms == 450.0
            assert stats.provider_fallbacks == 0

    def test_counts_fallbacks_from_provider_responses(self):
        mock_response_data = {
            "data": {
                "id": "gen-456",
                "latency": 900,
                "generation_time": 400,
                "cache_discount": None,
                "provider_name": "Google",
                "provider_responses": [
                    {"status": 503, "latency": 200},
                    {"status": 429, "latency": 100},
                    {"status": 200, "latency": 400},
                ],
                "native_tokens_cached": 0,
                "native_tokens_reasoning": 0,
                "streamed": False,
            }
        }

        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response_data
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-456", api_key="fake-key")
            assert stats.provider_fallbacks == 2

    def test_returns_none_on_http_error(self):
        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.raise_for_status.side_effect = Exception("Not Found")
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-bad", api_key="fake-key")
            assert stats is None

    def test_returns_none_when_generation_id_is_none(self):
        stats = fetch_generation_stats(None, api_key="fake-key")
        assert stats is None
```

### Step 2: Run tests to verify failure

### Step 3: Implement generation stats fetcher

**File:** `agent-evals/src/agent_evals/llm/generation_stats.py`

```python
"""Fetch post-hoc generation stats from OpenRouter API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OPENROUTER_GENERATION_URL = "https://openrouter.ai/api/v1/generation"


@dataclass
class GenerationStats:
    """Post-hoc metrics from OpenRouter's generation stats endpoint."""

    generation_id: str
    latency_ms: float | None
    generation_time_ms: float | None
    cache_discount: float | None
    provider_name: str | None
    provider_fallbacks: int
    native_tokens_cached: int
    native_tokens_reasoning: int
    streamed: bool | None


def fetch_generation_stats(
    generation_id: str | None,
    *,
    api_key: str,
) -> GenerationStats | None:
    """Fetch generation stats from OpenRouter.

    Returns None if generation_id is None or the request fails.
    """
    if generation_id is None:
        return None

    import httpx

    try:
        resp = httpx.get(
            OPENROUTER_GENERATION_URL,
            params={"id": generation_id},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except Exception:
        logger.warning(
            "Failed to fetch generation stats for %s", generation_id
        )
        return None

    provider_responses = data.get("provider_responses") or []
    fallbacks = sum(
        1 for pr in provider_responses if pr.get("status", 200) != 200
    )

    return GenerationStats(
        generation_id=generation_id,
        latency_ms=data.get("latency"),
        generation_time_ms=data.get("generation_time"),
        cache_discount=data.get("cache_discount"),
        provider_name=data.get("provider_name"),
        provider_fallbacks=fallbacks,
        native_tokens_cached=data.get("native_tokens_cached") or 0,
        native_tokens_reasoning=data.get("native_tokens_reasoning") or 0,
        streamed=data.get("streamed"),
    )
```

### Step 4: Run tests, verify pass

### Step 5: Commit

```bash
git commit -m "feat(llm): add OpenRouter generation stats fetcher"
```

---

## Task 3: CostMetrics Data Model

**Purpose:** Structured model aggregating all operational data per trial, stored in TrialResult.metrics.

**Files:**
- Create: `agent-evals/src/agent_evals/metrics.py`
- Create: `agent-evals/tests/test_metrics.py`

### Step 1: Write failing tests

**File:** `agent-evals/tests/test_metrics.py`

```python
"""Tests for operational metrics data models."""

from __future__ import annotations

import pytest

from agent_evals.metrics import CostMetrics, TurnMetrics, aggregate_turn_metrics


class TestCostMetrics:
    def test_construction_with_all_fields(self):
        m = CostMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=10,
            cached_tokens=80,
            cache_write_tokens=20,
            total_cost_usd=0.005,
            cache_discount_usd=0.003,
            latency_ms=450.0,
            generation_time_ms=380.0,
            provider="Anthropic",
            generation_id="gen-123",
            provider_fallbacks=0,
        )
        assert m.total_cost_usd == 0.005
        assert m.cache_hit_rate == 0.8  # 80/100

    def test_cache_hit_rate_zero_when_no_prompt_tokens(self):
        m = CostMetrics(
            prompt_tokens=0,
            completion_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=0.001,
            cache_discount_usd=None,
            latency_ms=None,
            generation_time_ms=None,
            provider=None,
            generation_id=None,
            provider_fallbacks=0,
        )
        assert m.cache_hit_rate == 0.0

    def test_to_dict_serializable(self):
        m = CostMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=0.005,
            cache_discount_usd=None,
            latency_ms=450.0,
            generation_time_ms=None,
            provider="Anthropic",
            generation_id="gen-123",
            provider_fallbacks=0,
        )
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d["prompt_tokens"] == 100
        assert d["provider"] == "Anthropic"


class TestTurnMetrics:
    def test_construction(self):
        t = TurnMetrics(
            turn=1,
            prompt_tokens=50,
            completion_tokens=25,
            cost_usd=0.001,
            api_call_ms=200.0,
            tool_name="read_doc",
        )
        assert t.turn == 1
        assert t.tool_name == "read_doc"


class TestAggregateTurnMetrics:
    def test_aggregates_across_turns(self):
        turns = [
            TurnMetrics(1, 50, 25, 0.001, 200.0, "list_docs"),
            TurnMetrics(2, 80, 30, 0.002, 300.0, "read_doc"),
            TurnMetrics(3, 100, 40, 0.003, 250.0, None),
        ]
        agg = aggregate_turn_metrics(turns)
        assert agg.prompt_tokens == 230
        assert agg.completion_tokens == 95
        assert abs(agg.total_cost_usd - 0.006) < 0.0001

    def test_empty_turns_returns_zero_metrics(self):
        agg = aggregate_turn_metrics([])
        assert agg.prompt_tokens == 0
        assert agg.total_cost_usd == 0.0
```

### Step 2: Run tests to verify failure

### Step 3: Implement metrics module

**File:** `agent-evals/src/agent_evals/metrics.py`

```python
"""Operational metrics data models for evaluation trials."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TurnMetrics:
    """Metrics for a single turn in a multi-turn strategy."""

    turn: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    api_call_ms: float
    tool_name: str | None = None


@dataclass
class CostMetrics:
    """Aggregated operational metrics for a single trial."""

    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    total_cost_usd: float | None
    cache_discount_usd: float | None
    latency_ms: float | None
    generation_time_ms: float | None
    provider: str | None
    generation_id: str | None
    provider_fallbacks: int
    turns: list[TurnMetrics] = field(default_factory=list)

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of prompt tokens served from cache."""
        if self.prompt_tokens == 0:
            return 0.0
        return self.cached_tokens / self.prompt_tokens

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict for storage in metrics."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_cost_usd": self.total_cost_usd,
            "cache_discount_usd": self.cache_discount_usd,
            "cache_hit_rate": self.cache_hit_rate,
            "latency_ms": self.latency_ms,
            "generation_time_ms": self.generation_time_ms,
            "provider": self.provider,
            "generation_id": self.generation_id,
            "provider_fallbacks": self.provider_fallbacks,
            "turns": [
                {
                    "turn": t.turn,
                    "prompt_tokens": t.prompt_tokens,
                    "completion_tokens": t.completion_tokens,
                    "cost_usd": t.cost_usd,
                    "api_call_ms": t.api_call_ms,
                    "tool_name": t.tool_name,
                }
                for t in self.turns
            ],
        }


def aggregate_turn_metrics(turns: list[TurnMetrics]) -> CostMetrics:
    """Aggregate per-turn metrics into a single CostMetrics."""
    if not turns:
        return CostMetrics(
            prompt_tokens=0,
            completion_tokens=0,
            reasoning_tokens=0,
            cached_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=0.0,
            cache_discount_usd=None,
            latency_ms=None,
            generation_time_ms=None,
            provider=None,
            generation_id=None,
            provider_fallbacks=0,
            turns=turns,
        )

    return CostMetrics(
        prompt_tokens=sum(t.prompt_tokens for t in turns),
        completion_tokens=sum(t.completion_tokens for t in turns),
        reasoning_tokens=0,
        cached_tokens=0,
        cache_write_tokens=0,
        total_cost_usd=sum(t.cost_usd for t in turns if t.cost_usd),
        cache_discount_usd=None,
        latency_ms=sum(t.api_call_ms for t in turns),
        generation_time_ms=None,
        provider=None,
        generation_id=None,
        provider_fallbacks=0,
        turns=turns,
    )
```

### Step 4: Run tests, verify pass

### Step 5: Commit

```bash
git commit -m "feat(metrics): add CostMetrics and TurnMetrics data models"
```

---

## Task 4: Wire Metrics into Runner

**Purpose:** Build CostMetrics from GenerationResult + GenerationStats and store in TrialResult.metrics.

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py` (lines 862-910, _run_trial)
- Modify: `agent-evals/tests/test_runner.py`

### Step 1: Write failing tests

Add tests that verify TrialResult.metrics contains a "cost_metrics" key with the expected structure after a trial.

### Step 2: Modify _run_trial() to build CostMetrics

After the existing metrics population (runner.py ~line 873), add:

```python
# Build CostMetrics from strategy result
from agent_evals.metrics import CostMetrics

first_gen = strategy_result.generations[0] if strategy_result.generations else None
cost_metrics = CostMetrics(
    prompt_tokens=strategy_result.total_prompt_tokens,
    completion_tokens=strategy_result.total_completion_tokens,
    reasoning_tokens=first_gen.reasoning_tokens if first_gen else 0,
    cached_tokens=first_gen.cached_tokens if first_gen else 0,
    cache_write_tokens=first_gen.cache_write_tokens if first_gen else 0,
    total_cost_usd=strategy_result.total_cost,
    cache_discount_usd=None,  # Populated by generation stats fetch
    latency_ms=first_gen.api_call_ms if first_gen else None,
    generation_time_ms=None,  # Populated by generation stats fetch
    provider=first_gen.provider if first_gen else None,
    generation_id=first_gen.generation_id if first_gen else None,
    provider_fallbacks=0,
)
metrics["cost_metrics"] = cost_metrics.to_dict()
```

### Step 3: Optionally fetch generation stats

Add config flag `fetch_generation_stats: bool = False` to EvalRunConfig. When enabled:

```python
if self._config.fetch_generation_stats and cost_metrics.generation_id:
    from agent_evals.llm.generation_stats import fetch_generation_stats

    stats = fetch_generation_stats(
        cost_metrics.generation_id,
        api_key=self._client.api_key,
    )
    if stats:
        metrics["cost_metrics"]["latency_ms"] = stats.latency_ms
        metrics["cost_metrics"]["generation_time_ms"] = stats.generation_time_ms
        metrics["cost_metrics"]["cache_discount_usd"] = stats.cache_discount
        metrics["cost_metrics"]["provider_fallbacks"] = stats.provider_fallbacks
```

### Step 4: Run tests, verify pass

### Step 5: Commit

```bash
git commit -m "feat(runner): build CostMetrics per trial with optional generation stats"
```

---

## Task 5: Stability Metrics

**Purpose:** Compute coefficient of variation, min/max spread, and consistency across repetitions.

**Files:**
- Create: `agent-evals/src/agent_evals/reports/stability.py`
- Create: `agent-evals/tests/test_stability.py`

### Step 1: Write failing tests

**File:** `agent-evals/tests/test_stability.py`

```python
"""Tests for stability metrics computation."""

from __future__ import annotations

import pytest

from agent_evals.reports.stability import (
    StabilityMetrics,
    compute_stability,
)


class TestComputeStability:
    def test_perfect_stability(self):
        scores = [0.8, 0.8, 0.8, 0.8, 0.8]
        result = compute_stability(scores)
        assert result.coefficient_of_variation == 0.0
        assert result.min_max_spread == 0.0

    def test_moderate_variance(self):
        scores = [0.7, 0.8, 0.75, 0.85, 0.9]
        result = compute_stability(scores)
        assert 0.0 < result.coefficient_of_variation < 0.2
        assert result.min_max_spread == pytest.approx(0.2)

    def test_high_variance(self):
        scores = [0.1, 0.9, 0.2, 0.8, 0.5]
        result = compute_stability(scores)
        assert result.coefficient_of_variation > 0.3

    def test_single_score_returns_zero_variance(self):
        result = compute_stability([0.5])
        assert result.coefficient_of_variation == 0.0
        assert result.min_max_spread == 0.0

    def test_empty_scores_returns_zero(self):
        result = compute_stability([])
        assert result.coefficient_of_variation == 0.0
        assert result.mean == 0.0

    def test_metrics_fields(self):
        result = compute_stability([0.6, 0.7, 0.8])
        assert hasattr(result, "mean")
        assert hasattr(result, "std_dev")
        assert hasattr(result, "coefficient_of_variation")
        assert hasattr(result, "min_max_spread")
        assert hasattr(result, "count")
```

### Step 2: Implement stability module

**File:** `agent-evals/src/agent_evals/reports/stability.py`

```python
"""Stability metrics for evaluation consistency analysis."""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class StabilityMetrics:
    """Consistency metrics across repeated runs."""

    mean: float
    std_dev: float
    coefficient_of_variation: float
    min_max_spread: float
    count: int


def compute_stability(scores: list[float]) -> StabilityMetrics:
    """Compute stability metrics from a list of scores.

    Coefficient of variation = std_dev / mean (0 = perfectly stable).
    Min/max spread = max - min across runs.
    """
    if len(scores) <= 1:
        mean = scores[0] if scores else 0.0
        return StabilityMetrics(
            mean=mean,
            std_dev=0.0,
            coefficient_of_variation=0.0,
            min_max_spread=0.0,
            count=len(scores),
        )

    mean = statistics.mean(scores)
    std_dev = statistics.stdev(scores)
    cv = std_dev / mean if mean != 0 else 0.0

    return StabilityMetrics(
        mean=mean,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        min_max_spread=max(scores) - min(scores),
        count=len(scores),
    )
```

### Step 3: Run tests, verify pass

### Step 4: Commit

```bash
git commit -m "feat(reports): add stability metrics (CV, min/max spread)"
```

---

## Task 6: Extend Reporting with Cost-Efficiency Tables

**Purpose:** Add cost-efficiency Pareto frontier and stability columns to variant summary reports.

**Files:**
- Modify: `agent-evals/src/agent_evals/reports/aggregator.py` (VariantSummary, ReportData)
- Create: `agent-evals/src/agent_evals/reports/cost_efficiency.py`
- Create: `agent-evals/tests/test_cost_efficiency.py`

### Step 1: Write failing tests

**File:** `agent-evals/tests/test_cost_efficiency.py`

```python
"""Tests for cost-efficiency reporting."""

from __future__ import annotations

import pytest

from agent_evals.reports.cost_efficiency import (
    CostEfficiencyRow,
    compute_pareto_frontier,
    render_cost_efficiency_table,
)


class TestComputeParetoFrontier:
    def test_identifies_pareto_optimal_points(self):
        rows = [
            CostEfficiencyRow("A", accuracy=0.82, cost=0.004, stability=0.03),
            CostEfficiencyRow("B", accuracy=0.84, cost=0.009, stability=0.05),
            CostEfficiencyRow("C", accuracy=0.71, cost=0.003, stability=0.02),
            CostEfficiencyRow("D", accuracy=0.60, cost=0.010, stability=0.10),
        ]
        frontier = compute_pareto_frontier(rows)
        names = {r.variant for r in frontier}
        # A dominates D (better accuracy AND lower cost)
        assert "D" not in names
        # A is Pareto optimal (good accuracy, low cost)
        assert "A" in names
        # C is Pareto optimal (lowest cost)
        assert "C" in names

    def test_single_row_is_pareto_optimal(self):
        rows = [CostEfficiencyRow("only", 0.8, 0.005, 0.02)]
        frontier = compute_pareto_frontier(rows)
        assert len(frontier) == 1

    def test_empty_returns_empty(self):
        assert compute_pareto_frontier([]) == []


class TestRenderCostEfficiencyTable:
    def test_renders_readable_table(self):
        rows = [
            CostEfficiencyRow("2-tier-md", 82.3, 0.0041, 3.0, pareto=True),
            CostEfficiencyRow("flat-md", 71.2, 0.0028, 2.0, pareto=False),
        ]
        text = render_cost_efficiency_table(rows)
        assert "2-tier-md" in text
        assert "Pareto" in text or "optimal" in text.lower()
        assert "flat-md" in text
```

### Step 2: Implement cost efficiency module

**File:** `agent-evals/src/agent_evals/reports/cost_efficiency.py`

```python
"""Cost-efficiency analysis and Pareto frontier computation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostEfficiencyRow:
    """A single variant's cost-efficiency profile."""

    variant: str
    accuracy: float
    cost: float
    stability: float
    cache_hit_rate: float = 0.0
    pareto: bool = False


def compute_pareto_frontier(
    rows: list[CostEfficiencyRow],
) -> list[CostEfficiencyRow]:
    """Identify Pareto-optimal variants (higher accuracy, lower cost).

    A variant is Pareto-optimal if no other variant has both
    higher accuracy AND lower cost.
    """
    if not rows:
        return []

    frontier = []
    for candidate in rows:
        dominated = False
        for other in rows:
            if other is candidate:
                continue
            if (
                other.accuracy >= candidate.accuracy
                and other.cost <= candidate.cost
                and (
                    other.accuracy > candidate.accuracy
                    or other.cost < candidate.cost
                )
            ):
                dominated = True
                break
        if not dominated:
            candidate.pareto = True
            frontier.append(candidate)

    return frontier


def render_cost_efficiency_table(rows: list[CostEfficiencyRow]) -> str:
    """Render a cost-efficiency comparison table."""
    if not rows:
        return "No data available."

    sorted_rows = sorted(rows, key=lambda r: r.accuracy, reverse=True)

    header = (
        f"{'VARIANT':<25s} {'ACCURACY':>10s} {'COST/TRIAL':>12s} "
        f"{'CACHE HIT':>10s} {'VARIANCE':>10s} {'STATUS':>16s}"
    )
    sep = "-" * len(header)
    lines = [header, sep]

    for r in sorted_rows:
        status = "Pareto optimal" if r.pareto else ""
        lines.append(
            f"{r.variant:<25s} {r.accuracy:>9.1f}% "
            f"${r.cost:>10.4f} {r.cache_hit_rate:>9.0f}% "
            f"{r.stability:>9.1f}% {status:>16s}"
        )

    return "\n".join(lines)
```

### Step 3: Run tests, verify pass

### Step 4: Commit

```bash
git commit -m "feat(reports): add cost-efficiency Pareto frontier analysis"
```

---

## Task 7: Multi-Objective Taguchi Analysis

**Purpose:** Enable running Taguchi screening on cost and latency as response variables alongside accuracy.

**Files:**
- Modify: `agent-evals/src/agent_evals/taguchi/analysis.py`
- Create: `agent-evals/tests/test_taguchi_multi_objective.py`

### Step 1: Write failing tests

**File:** `agent-evals/tests/test_taguchi_multi_objective.py`

```python
"""Tests for multi-objective Taguchi analysis."""

from __future__ import annotations

import pytest

from agent_evals.taguchi.analysis import compute_sn_ratios


class TestMultiObjectiveSNRatios:
    def test_smaller_is_better_for_cost(self):
        """Lower cost = better, so smaller_is_better quality type."""
        row_costs = {
            0: [0.005, 0.006, 0.004],  # Low cost
            1: [0.020, 0.025, 0.018],  # High cost
        }
        sn = compute_sn_ratios(row_costs, quality_type="smaller_is_better")
        # Low-cost row should have higher (less negative) S/N ratio
        assert sn[0] > sn[1]

    def test_smaller_is_better_for_latency(self):
        """Lower latency = better."""
        row_latencies = {
            0: [200.0, 220.0, 180.0],  # Fast
            1: [800.0, 900.0, 750.0],  # Slow
        }
        sn = compute_sn_ratios(
            row_latencies, quality_type="smaller_is_better"
        )
        assert sn[0] > sn[1]

    def test_nominal_is_best_for_stability(self):
        """Consistency = good, so nominal_is_best quality type."""
        row_scores = {
            0: [0.80, 0.80, 0.80],  # Stable
            1: [0.90, 0.50, 0.70],  # Unstable (same mean ~0.70)
        }
        sn = compute_sn_ratios(
            row_scores, quality_type="nominal_is_best"
        )
        # Stable row should have higher S/N
        assert sn[0] > sn[1]
```

### Step 2: Run tests — these should already pass

The exploration showed `compute_sn_ratios` already supports all three quality types (lines 118-141 of analysis.py). This test verifies that existing code works for our Phase B use case.

### Step 3: Add multi-objective wrapper if needed

If the tests pass, the existing code supports multi-objective analysis. Add a convenience function:

**File:** `agent-evals/src/agent_evals/taguchi/multi_objective.py`

```python
"""Multi-objective Taguchi analysis for cost, latency, and accuracy."""

from __future__ import annotations

from agent_evals.taguchi.analysis import (
    compute_main_effects,
    compute_sn_ratios,
    run_anova,
)


def run_multi_objective_analysis(
    design,
    row_scores: dict[int, list[float]],
    row_costs: dict[int, list[float]],
    row_latencies: dict[int, list[float]],
) -> dict[str, dict]:
    """Run Taguchi analysis on accuracy, cost, and latency simultaneously.

    Returns a dict keyed by objective name with S/N ratios,
    main effects, and ANOVA results for each.
    """
    objectives = {
        "accuracy": ("larger_is_better", row_scores),
        "cost": ("smaller_is_better", row_costs),
        "latency": ("smaller_is_better", row_latencies),
    }

    results = {}
    for name, (quality_type, row_data) in objectives.items():
        if not row_data:
            continue
        sn = compute_sn_ratios(row_data, quality_type=quality_type)
        effects = compute_main_effects(design, sn)
        anova = run_anova(design, sn)
        results[name] = {
            "sn_ratios": sn,
            "main_effects": effects,
            "anova": anova,
        }

    return results
```

### Step 4: Write test for multi-objective wrapper, run, verify

### Step 5: Commit

```bash
git commit -m "feat(taguchi): add multi-objective analysis for cost/latency/accuracy"
```

---

## Task 8: Integration Tests and Final Verification

**Files:**
- Create: `agent-evals/tests/test_integration_phase_b.py`

### Step 1: Write integration tests

```python
"""Phase B integration tests — operational metrics pipeline."""

from __future__ import annotations

import pytest

from agent_evals.llm.client import GenerationResult
from agent_evals.llm.generation_stats import GenerationStats
from agent_evals.metrics import CostMetrics, TurnMetrics, aggregate_turn_metrics
from agent_evals.reports.cost_efficiency import (
    CostEfficiencyRow,
    compute_pareto_frontier,
    render_cost_efficiency_table,
)
from agent_evals.reports.stability import compute_stability


class TestMetricsPipelineIntegration:
    def test_generation_result_to_cost_metrics(self):
        """GenerationResult fields populate CostMetrics correctly."""
        gen = GenerationResult(
            content="response",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.005,
            model="test-model",
            generation_id="gen-123",
            api_call_ms=450.0,
            cached_tokens=80,
            cache_write_tokens=20,
            reasoning_tokens=10,
            provider="Anthropic",
        )
        metrics = CostMetrics(
            prompt_tokens=gen.prompt_tokens,
            completion_tokens=gen.completion_tokens,
            reasoning_tokens=gen.reasoning_tokens,
            cached_tokens=gen.cached_tokens,
            cache_write_tokens=gen.cache_write_tokens,
            total_cost_usd=gen.cost,
            cache_discount_usd=None,
            latency_ms=gen.api_call_ms,
            generation_time_ms=None,
            provider=gen.provider,
            generation_id=gen.generation_id,
            provider_fallbacks=0,
        )
        assert metrics.cache_hit_rate == 0.8
        d = metrics.to_dict()
        assert d["provider"] == "Anthropic"

    def test_stability_feeds_cost_efficiency(self):
        """Stability metrics integrate with cost-efficiency rows."""
        scores = [0.80, 0.82, 0.78, 0.81, 0.79]
        stability = compute_stability(scores)

        row = CostEfficiencyRow(
            variant="2-tier-md",
            accuracy=stability.mean * 100,
            cost=0.004,
            stability=stability.coefficient_of_variation * 100,
        )
        assert row.accuracy > 0
        assert row.stability < 10  # Low CV = stable

    def test_pareto_and_render_pipeline(self):
        """Full pipeline: metrics → Pareto → rendered table."""
        rows = [
            CostEfficiencyRow("A", 82.0, 0.004, 3.0),
            CostEfficiencyRow("B", 71.0, 0.003, 2.0),
            CostEfficiencyRow("C", 60.0, 0.010, 10.0),
        ]
        frontier = compute_pareto_frontier(rows)
        assert len(frontier) >= 1

        text = render_cost_efficiency_table(rows)
        assert "A" in text
```

### Step 2: Run all tests with coverage

```bash
~/.local/bin/uv run pytest agent-evals/tests/ --cov=agent_evals --cov-report=term-missing -v 2>&1 | tail -30
```

### Step 3: Lint and type check new files

```bash
~/.local/bin/uv run ruff check agent-evals/src/agent_evals/metrics.py \
    agent-evals/src/agent_evals/llm/generation_stats.py \
    agent-evals/src/agent_evals/reports/stability.py \
    agent-evals/src/agent_evals/reports/cost_efficiency.py

~/.local/bin/uv run mypy agent-evals/src/agent_evals/metrics.py \
    agent-evals/src/agent_evals/llm/generation_stats.py
```

### Step 4: Commit

```bash
git commit -m "test: add Phase B integration tests — metrics pipeline verified"
```

---

## Summary

| Task | What | Tests | Commits |
|------|------|-------|---------|
| 0 | Verify Phase A baseline | — | — |
| 1 | Extend GenerationResult with OpenRouter metadata | ~7 tests | 1 |
| 2 | Generation stats fetcher | ~5 tests | 1 |
| 3 | CostMetrics data model | ~7 tests | 1 |
| 4 | Wire metrics into runner | ~4 tests | 1 |
| 5 | Stability metrics | ~6 tests | 1 |
| 6 | Cost-efficiency Pareto tables | ~4 tests | 1 |
| 7 | Multi-objective Taguchi | ~4 tests | 1 |
| 8 | Integration tests | ~3 tests | 1 |
| **Total** | | **~40 tests** | **~8 commits** |
