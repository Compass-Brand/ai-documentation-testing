"""Multi-model LLM client pool for Taguchi evaluation runs.

Manages a pool of :class:`LLMClient` instances (one per model) with
optional per-model and global budget tracking. Thread-safe for
concurrent trial execution.
"""

from __future__ import annotations

import threading
from typing import Any

from agent_evals.llm.client import LLMClient


class LLMClientPool:
    """Pool of LLM clients for multi-model evaluation runs.

    Creates :class:`LLMClient` instances lazily on first access and
    caches them for the pool's lifetime. Supports per-model and global
    budget caps with thread-safe cost recording.

    Args:
        models: List of model name strings to manage.
        api_key: API key passed to all clients.
        provider_config: Optional provider config passed to all clients.
        temperature: Temperature setting for all clients.
        model_budgets: Optional per-model budget caps (model_name -> dollars).
        global_budget: Optional total spend cap across all models.
    """

    def __init__(
        self,
        models: list[str],
        api_key: str,
        provider_config: dict[str, Any] | None = None,
        temperature: float = 0.3,
        model_budgets: dict[str, float] | None = None,
        global_budget: float | None = None,
    ) -> None:
        self._model_names: list[str] = list(models)
        self._model_set: frozenset[str] = frozenset(models)
        self._api_key = api_key
        self._provider_config = provider_config
        self._temperature = temperature
        self._model_budgets: dict[str, float] = dict(model_budgets or {})
        self._global_budget: float | None = global_budget

        self._clients: dict[str, LLMClient] = {}
        self._costs: dict[str, float] = {m: 0.0 for m in models}
        self._lock = threading.Lock()

    @property
    def models(self) -> list[str]:
        """Return the list of configured model names (insertion order)."""
        return list(self._model_names)

    def get_all_models(self) -> list[str]:
        """Return all configured model names. Alias for :attr:`models`."""
        return self.models

    def _validate_model(self, model_name: str) -> None:
        """Raise KeyError if *model_name* is not in the pool."""
        if model_name not in self._model_set:
            msg = f"Model not in pool: {model_name!r}"
            raise KeyError(msg)

    def get_client(self, model_name: str) -> LLMClient:
        """Return the :class:`LLMClient` for *model_name*, creating lazily.

        Thread-safe: concurrent calls for the same model return the
        same instance.

        Raises:
            KeyError: If *model_name* was not in the pool's model list.
        """
        self._validate_model(model_name)
        with self._lock:
            if model_name not in self._clients:
                self._clients[model_name] = LLMClient(
                    model=model_name,
                    api_key=self._api_key,
                    provider_config=self._provider_config,
                    temperature=self._temperature,
                )
            return self._clients[model_name]

    def record_cost(self, model_name: str, cost: float) -> None:
        """Record a cost against *model_name*. Thread-safe.

        Raises:
            KeyError: If *model_name* is not in the pool.
        """
        self._validate_model(model_name)
        with self._lock:
            self._costs[model_name] += cost

    def get_model_cost(self, model_name: str) -> float:
        """Return total accumulated cost for *model_name*.

        Raises:
            KeyError: If *model_name* is not in the pool.
        """
        self._validate_model(model_name)
        with self._lock:
            return self._costs[model_name]

    def is_budget_exceeded(self, model_name: str) -> bool:
        """Check whether *model_name* has exceeded its per-model budget.

        Returns ``False`` if no per-model budget is set for this model.
        """
        self._validate_model(model_name)
        budget = self._model_budgets.get(model_name)
        if budget is None:
            return False
        with self._lock:
            return self._costs[model_name] > budget

    def is_global_budget_exceeded(self) -> bool:
        """Check whether total spend across all models exceeds the global cap.

        Returns ``False`` if no global budget is configured.
        """
        if self._global_budget is None:
            return False
        with self._lock:
            total = sum(self._costs.values())
            return total > self._global_budget

    def get_budget_state(self) -> dict[str, Any]:
        """Return a snapshot of budget state for dashboard/reporting.

        Returns a dict with keys:
            - ``global_budget``: The global cap or ``None``.
            - ``global_spent``: Total spend across all models.
            - ``models``: Dict of model_name -> {spent, budget}.
        """
        with self._lock:
            model_states: dict[str, dict[str, Any]] = {}
            for name in self._model_names:
                model_states[name] = {
                    "spent": self._costs[name],
                    "budget": self._model_budgets.get(name),
                }
            return {
                "global_budget": self._global_budget,
                "global_spent": sum(self._costs.values()),
                "models": model_states,
            }
