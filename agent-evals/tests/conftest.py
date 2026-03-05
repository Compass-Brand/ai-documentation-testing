"""Shared test configuration and factories for agent-evals tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add agent-evals root to sys.path so that `pilot` package is importable
_AGENT_EVALS_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_EVALS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_EVALS_ROOT))


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------


def make_mock_task(
    task_id: str = "retrieval_001",
    *,
    task_type: str = "retrieval",
    score: float = 0.8,
    prompt: list[dict[str, str]] | None = None,
) -> MagicMock:
    """Create a mock EvalTask.

    Args:
        task_id: Task identifier (positional for convenience).
        task_type: Task type string stored on definition.type.
        score: Value returned by score_response().
        prompt: Messages returned by build_prompt(). Defaults to a
            single user message.
    """
    task = MagicMock()
    task.definition.task_id = task_id
    task.definition.type = task_type
    task.build_prompt.return_value = prompt or [
        {"role": "user", "content": "test question"},
    ]
    task.score_response.return_value = score
    return task


def make_mock_client(
    model: str = "mock-model",
    *,
    content: str | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    cost: float | None = 0.001,
    generation_id: str | None = None,
) -> MagicMock:
    """Create a mock LLMClient.

    Args:
        model: Model name (positional for convenience).
        content: Response content. Defaults to ``"response from {model}"``.
        prompt_tokens: Prompt token count on the generation result.
        completion_tokens: Completion token count on the generation result.
        total_tokens: Total token count on the generation result.
        cost: Cost value on the generation result.
        generation_id: Optional generation ID.
    """
    client = MagicMock()
    client.model = model

    gen = MagicMock()
    gen.content = content if content is not None else f"response from {model}"
    gen.prompt_tokens = prompt_tokens
    gen.completion_tokens = completion_tokens
    gen.total_tokens = total_tokens
    gen.cost = cost
    gen.model = model
    gen.generation_id = generation_id

    client.complete.return_value = gen
    return client


def make_mock_variant(
    name: str = "flat",
    axis: int = 1,
    *,
    token_estimate: int = 100,
    rendered: str | None = None,
) -> MagicMock:
    """Create a mock IndexVariant.

    Args:
        name: Variant name (positional for convenience).
        axis: Axis number (positional for convenience).
        token_estimate: Token estimate in metadata.
        rendered: String returned by render(). Defaults to
            ``"rendered {name}"``.
    """
    variant = MagicMock()
    meta = MagicMock()
    meta.name = name
    meta.token_estimate = token_estimate
    variant.metadata.return_value = meta
    variant.render.return_value = rendered if rendered is not None else f"rendered {name}"
    return variant


# ---------------------------------------------------------------------------
# Context strategy mock factories (Phase 1 preparation)
# ---------------------------------------------------------------------------


def make_mock_strategy(
    *,
    prepared_messages: list[dict[str, str]] | None = None,
    prepared_tools: list[dict] | None = None,
    strategy_metadata: dict | None = None,
    final_response: str = "strategy response",
    total_prompt_tokens: int = 100,
    total_completion_tokens: int = 50,
    total_tokens: int = 150,
    total_cost: float | None = 0.005,
) -> MagicMock:
    """Create a mock ContextStrategy.

    The mock has ``prepare()`` returning a PreparedContext-shaped object
    and ``execute()`` returning a StrategyResult-shaped object.  The real
    classes will be created in Phase 1; these mocks match the planned
    interface so tests can be written ahead of time.
    """
    strategy = MagicMock()

    # prepare() -> PreparedContext-shaped mock
    prepared = MagicMock()
    prepared.messages = prepared_messages or [
        {"role": "user", "content": "test question"},
    ]
    prepared.tools = prepared_tools
    prepared.strategy_metadata = strategy_metadata or {}
    strategy.prepare.return_value = prepared

    # execute() -> StrategyResult-shaped mock
    result = MagicMock()
    result.final_response = final_response
    result.generations = []
    result.total_prompt_tokens = total_prompt_tokens
    result.total_completion_tokens = total_completion_tokens
    result.total_tokens = total_tokens
    result.total_cost = total_cost
    result.messages = prepared.messages
    result.strategy_metadata = prepared.strategy_metadata
    strategy.execute.return_value = result

    return strategy


def make_prepared_context(
    *,
    messages: list[dict[str, str]] | None = None,
    tools: list[dict] | None = None,
    strategy_metadata: dict | None = None,
) -> MagicMock:
    """Create a mock PreparedContext.

    Matches the planned interface:
      - messages: list[dict] -- prompt messages
      - tools: list[dict] | None -- optional tool definitions
      - strategy_metadata: dict -- strategy-specific metadata
    """
    ctx = MagicMock()
    ctx.messages = messages or [{"role": "user", "content": "test question"}]
    ctx.tools = tools
    ctx.strategy_metadata = strategy_metadata or {}
    return ctx


def make_strategy_result(
    *,
    final_response: str = "strategy response",
    generations: list | None = None,
    total_prompt_tokens: int = 100,
    total_completion_tokens: int = 50,
    total_tokens: int = 150,
    total_cost: float | None = 0.005,
    messages: list[dict[str, str]] | None = None,
    strategy_metadata: dict | None = None,
) -> MagicMock:
    """Create a mock StrategyResult wrapping GenerationResult.

    Matches the planned interface:
      - final_response: str -- the final LLM response text
      - generations: list -- list of GenerationResult objects
      - total_prompt_tokens / total_completion_tokens / total_tokens: int
      - total_cost: float | None
      - messages: list[dict] -- conversation messages
      - strategy_metadata: dict -- strategy-specific metadata
    """
    result = MagicMock()
    result.final_response = final_response
    result.generations = generations or []
    result.total_prompt_tokens = total_prompt_tokens
    result.total_completion_tokens = total_completion_tokens
    result.total_tokens = total_tokens
    result.total_cost = total_cost
    result.messages = messages or [{"role": "user", "content": "test question"}]
    result.strategy_metadata = strategy_metadata or {}
    return result
