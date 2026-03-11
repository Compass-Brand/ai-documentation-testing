"""Bug #196: ToolBasedStrategy.execute() turns zero total cost into None.

When all generation costs are 0.0, ``sum([0.0, 0.0]) or None`` evaluates to
None because 0.0 is falsy in Python.  The cost should be reported as 0.0,
not None.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agent_evals.context.tool_based import ToolBasedStrategy


def _make_zero_cost_client() -> MagicMock:
    """Create a mock LLMClient whose generations have cost=0.0."""
    client = MagicMock()
    gen = MagicMock()
    gen.content = "answer from the model"
    gen.prompt_tokens = 10
    gen.completion_tokens = 5
    gen.total_tokens = 15
    gen.cost = 0.0
    gen.tool_calls = None  # no tool calls → single turn
    client.complete.return_value = gen
    return client


def _make_prepared_context() -> MagicMock:
    """Create a minimal PreparedContext for ToolBasedStrategy.execute()."""
    ctx = MagicMock()
    ctx.messages = [
        {"role": "system", "content": "You are a doc assistant."},
        {"role": "user", "content": "What is auth?"},
    ]
    ctx.tools = []
    ctx.strategy_metadata = {}
    return ctx


def _make_task() -> MagicMock:
    """Create a minimal mock task."""
    task = MagicMock()
    task.definition.task_id = "retrieval_001"
    task.definition.type = "retrieval"
    return task


class TestZeroCostNotNone:
    """Bug #196: sum of zero costs should be 0.0, not None."""

    def test_should_return_zero_cost_when_all_generations_cost_zero(self) -> None:
        """When every generation has cost=0.0, total_cost must be 0.0."""
        strategy = ToolBasedStrategy(max_turns=3)
        client = _make_zero_cost_client()
        prepared = _make_prepared_context()
        task = _make_task()

        result = strategy.execute(
            prepared, task, client, max_tokens=256, temperature=0.0,
        )

        # The bug: ``sum([0.0]) or None`` returns None because 0.0 is falsy
        assert result.total_cost is not None, (
            "total_cost should be 0.0, not None (bug #196: falsy 0.0 check)"
        )
        assert result.total_cost == 0.0

    def test_should_return_none_cost_when_all_generations_cost_none(self) -> None:
        """When every generation has cost=None, total_cost should be None."""
        strategy = ToolBasedStrategy(max_turns=3)
        client = MagicMock()

        gen = MagicMock()
        gen.content = "answer"
        gen.prompt_tokens = 10
        gen.completion_tokens = 5
        gen.total_tokens = 15
        gen.cost = None
        gen.tool_calls = None
        client.complete.return_value = gen

        prepared = _make_prepared_context()
        task = _make_task()

        result = strategy.execute(
            prepared, task, client, max_tokens=256, temperature=0.0,
        )

        assert result.total_cost is None, (
            "total_cost should be None when no generation has a cost"
        )

    def test_should_return_positive_cost_when_costs_are_positive(self) -> None:
        """Sanity check: positive costs still sum correctly."""
        strategy = ToolBasedStrategy(max_turns=3)
        client = MagicMock()

        gen = MagicMock()
        gen.content = "answer"
        gen.prompt_tokens = 10
        gen.completion_tokens = 5
        gen.total_tokens = 15
        gen.cost = 0.005
        gen.tool_calls = None
        client.complete.return_value = gen

        prepared = _make_prepared_context()
        task = _make_task()

        result = strategy.execute(
            prepared, task, client, max_tokens=256, temperature=0.0,
        )

        assert result.total_cost == 0.005
