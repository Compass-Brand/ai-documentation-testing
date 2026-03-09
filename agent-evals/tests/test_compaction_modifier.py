"""Tests for multi-session persistence via simulated compaction.

Tests cover:
- simulate_compaction() truncation and system message preservation
- CompactionModifier wrapping an inner strategy
- run_compacted_sequence() multi-task execution with compaction
- format_durability_score() accuracy degradation measurement
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from conftest import make_mock_client, make_mock_task

from agent_evals.context.base import PreparedContext, StrategyResult


# ---------------------------------------------------------------------------
# simulate_compaction
# ---------------------------------------------------------------------------


class TestCompactionSimulator:
    """simulate_compaction() truncates conversations while preserving context."""

    def test_compacts_long_conversation(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction

        messages = [
            {"role": "user", "content": "A" * 100},
            {"role": "assistant", "content": "B" * 100},
            {"role": "user", "content": "C" * 100},
            {"role": "assistant", "content": "D" * 100},
        ]
        result = simulate_compaction(messages, target_ratio=0.5)
        # Should have fewer total characters than original
        original_chars = sum(len(m["content"]) for m in messages)
        result_chars = sum(len(m["content"]) for m in result)
        assert result_chars < original_chars
        # Should still have messages
        assert len(result) > 0

    def test_preserves_system_message(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "A" * 200},
            {"role": "assistant", "content": "B" * 200},
            {"role": "user", "content": "C" * 200},
            {"role": "assistant", "content": "D" * 200},
        ]
        result = simulate_compaction(messages, target_ratio=0.3)
        # System message must be first
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helpful assistant."

    def test_returns_valid_message_format(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello " * 50},
            {"role": "assistant", "content": "Response " * 50},
            {"role": "user", "content": "Follow-up " * 50},
        ]
        result = simulate_compaction(messages, target_ratio=0.5)
        # Every message must have role and content keys
        for msg in result:
            assert "role" in msg, "Missing 'role' key in message"
            assert "content" in msg, "Missing 'content' key in message"
            assert isinstance(msg["role"], str)
            assert isinstance(msg["content"], str)


# ---------------------------------------------------------------------------
# CompactionModifier
# ---------------------------------------------------------------------------


class TestCompactionModifier:
    """CompactionModifier wraps an inner strategy with compaction."""

    def test_wraps_strategy_with_compaction(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier
        from agent_evals.context.full import FullContextStrategy

        inner = FullContextStrategy()
        modifier = CompactionModifier(inner, compaction_ratio=0.5)
        assert modifier.name() == "full_context+compaction"
        assert modifier.supports_caching() is False

    def test_modifier_applies_compaction_between_phases(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier

        # Build a mock inner strategy that returns a long conversation
        inner = MagicMock()
        inner.name.return_value = "mock_strategy"
        inner.prepare.return_value = PreparedContext(
            messages=[{"role": "user", "content": "test"}],
            tools=None,
            strategy_metadata={},
        )
        # Inner execute returns messages with substantial content
        inner_result = StrategyResult(
            final_response="answer",
            generations=[],
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            total_cost=0.005,
            messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "X" * 200},
                {"role": "assistant", "content": "Y" * 200},
                {"role": "user", "content": "Z" * 200},
                {"role": "assistant", "content": "W" * 200},
            ],
            strategy_metadata={},
        )
        inner.execute.return_value = inner_result

        modifier = CompactionModifier(inner, compaction_ratio=0.4)
        task = make_mock_task()
        client = make_mock_client()
        prepared = modifier.prepare("index", task, None)
        result = modifier.execute(prepared, task, client, max_tokens=1024, temperature=0.0)

        # Compaction metadata should be present
        assert result.strategy_metadata["compaction_applied"] is True
        assert result.strategy_metadata["compaction_ratio"] == 0.4
        assert result.strategy_metadata["pre_compaction_messages"] == 5
        # Post-compaction should have fewer or equal messages
        assert result.strategy_metadata["post_compaction_messages"] <= 5
        # Messages should be compacted
        assert len(result.messages) <= len(inner_result.messages)


# ---------------------------------------------------------------------------
# run_compacted_sequence
# ---------------------------------------------------------------------------


class TestMultiTaskSequence:
    """run_compacted_sequence() applies compaction between tasks."""

    def test_multi_task_sequence_applies_compaction_between_tasks(self):
        from agent_evals.context.modifiers.compaction import run_compacted_sequence

        # Create a mock strategy
        strategy = MagicMock()
        strategy.prepare.return_value = PreparedContext(
            messages=[
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Question"},
            ],
            tools=None,
            strategy_metadata={},
        )
        strategy.execute.return_value = StrategyResult(
            final_response="answer",
            generations=[],
            total_prompt_tokens=50,
            total_completion_tokens=25,
            total_tokens=75,
            total_cost=0.002,
            messages=[
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Question " * 30},
                {"role": "assistant", "content": "Answer " * 30},
            ],
            strategy_metadata={},
        )

        tasks = [make_mock_task(f"task_{i}") for i in range(3)]
        client = make_mock_client()

        results = run_compacted_sequence(tasks, strategy, client, compaction_ratio=0.5)

        assert len(results) == 3
        # First task should not have compaction applied
        assert results[0].strategy_metadata["sequence_position"] == 0
        assert results[0].strategy_metadata["compaction_applied"] is False
        # Subsequent tasks should have compaction applied
        assert results[1].strategy_metadata["sequence_position"] == 1
        assert results[1].strategy_metadata["compaction_applied"] is True
        assert results[2].strategy_metadata["sequence_position"] == 2
        assert results[2].strategy_metadata["compaction_applied"] is True

    def test_format_durability_score(self):
        from agent_evals.context.modifiers.compaction import format_durability_score

        # Perfect durability: all scores equal
        results_perfect = [
            {"position": 0, "score": 1.0},
            {"position": 1, "score": 1.0},
            {"position": 2, "score": 1.0},
        ]
        assert format_durability_score(results_perfect) == 1.0

        # Some degradation
        results_degraded = [
            {"position": 0, "score": 1.0},
            {"position": 1, "score": 0.8},
            {"position": 2, "score": 0.6},
        ]
        score = format_durability_score(results_degraded)
        assert 0.0 < score < 1.0
        assert abs(score - 0.7) < 0.01  # (0.8 + 0.6) / 2 = 0.7

        # Empty or single result
        assert format_durability_score([]) == 1.0
        assert format_durability_score([{"position": 0, "score": 0.9}]) == 1.0

        # Zero first score
        results_zero = [
            {"position": 0, "score": 0.0},
            {"position": 1, "score": 0.5},
        ]
        assert format_durability_score(results_zero) == 0.0


# ---------------------------------------------------------------------------
# Related task sequence carryover
# ---------------------------------------------------------------------------


class TestRelatedTaskSequenceCarryover:
    """Compaction should allow testing whether context carries over between related tasks."""

    def test_related_task_sequence_tests_carryover(self):
        from agent_evals.context.modifiers.compaction import (
            CompactionModifier,
            run_compacted_sequence,
        )

        # Build a strategy that tracks calls and returns growing conversations
        call_count = {"n": 0}

        inner = MagicMock()
        inner.name.return_value = "test_strategy"

        def mock_prepare(rendered_index, task, doc_tree):
            return PreparedContext(
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": f"Task question {call_count['n']}"},
                ],
                tools=None,
                strategy_metadata={},
            )

        def mock_execute(prepared, task, client, max_tokens, temperature):
            call_count["n"] += 1
            return StrategyResult(
                final_response=f"Answer {call_count['n']}",
                generations=[],
                total_prompt_tokens=50,
                total_completion_tokens=25,
                total_tokens=75,
                total_cost=0.002,
                messages=prepared.messages + [
                    {"role": "assistant", "content": f"Answer {call_count['n']} " * 20},
                ],
                strategy_metadata={},
            )

        inner.prepare.side_effect = mock_prepare
        inner.execute.side_effect = mock_execute

        tasks = [make_mock_task(f"related_{i}") for i in range(3)]
        client = make_mock_client()

        results = run_compacted_sequence(tasks, inner, client, compaction_ratio=0.6)

        # All 3 tasks should produce results
        assert len(results) == 3
        # Each result should have the correct sequence position
        for i, result in enumerate(results):
            assert result.strategy_metadata["sequence_position"] == i
        # The later tasks should show compaction was applied
        assert results[0].strategy_metadata["compaction_applied"] is False
        assert results[1].strategy_metadata["compaction_applied"] is True
        assert results[2].strategy_metadata["compaction_applied"] is True
