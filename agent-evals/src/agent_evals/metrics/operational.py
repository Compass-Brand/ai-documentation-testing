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
