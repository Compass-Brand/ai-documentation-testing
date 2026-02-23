"""Rich terminal dashboard for live evaluation run monitoring.

Renders progress, per-model stats, budget status, and an alert feed
using Rich renderables.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent_evals.observatory.tracker import EventTracker


class TerminalDashboard:
    """Rich-based terminal dashboard for evaluation runs.

    Args:
        tracker: The EventTracker providing live stats.
        total_trials: Total planned trials for progress display.
        budget: Optional global budget cap for display.
    """

    def __init__(
        self,
        tracker: EventTracker,
        total_trials: int = 0,
        budget: float | None = None,
    ) -> None:
        self._tracker = tracker
        self._total_trials = total_trials
        self._budget = budget
        self._alerts: list[str] = []

    def add_alert(self, message: str) -> None:
        """Add an alert message to the feed."""
        self._alerts.append(message)

    def render(self, console: Console) -> None:
        """Render the full dashboard to the given console."""
        stats = self._tracker.stats
        console.print(self._build_progress(stats))
        console.print(self._build_model_table(stats))
        if self._budget is not None:
            console.print(self._build_budget(stats))
        if self._alerts:
            console.print(self._build_alerts())

    def _build_progress(self, stats: dict) -> Panel:
        """Build the progress panel."""
        completed = stats["total_trials"]
        total = self._total_trials
        if total > 0:
            pct = completed / total * 100
            text = Text(f"{completed} / {total} trials ({pct:.0f}%)")
        else:
            text = Text(f"{completed} trials completed")
        return Panel(text, title="Progress")

    def _build_model_table(self, stats: dict) -> Table:
        """Build per-model stats table."""
        table = Table(title="Model Stats")
        table.add_column("Model")
        table.add_column("Trials", justify="right")
        table.add_column("Total Cost", justify="right")
        table.add_column("Avg Cost", justify="right")

        per_model = stats.get("per_model", {})
        for model_name, ms in sorted(per_model.items()):
            table.add_row(
                model_name,
                str(ms["count"]),
                f"${ms['total_cost']:.4f}",
                f"${ms['average_cost']:.4f}",
            )
        return table

    def _build_budget(self, stats: dict) -> Panel:
        """Build budget display panel."""
        spent = stats["total_cost"]
        budget = self._budget or 0.0
        text = Text(f"${spent:.2f} / ${budget:.2f}")
        return Panel(text, title="Budget")

    def _build_alerts(self) -> Panel:
        """Build alert feed panel."""
        alert_text = Text("\n".join(self._alerts))
        return Panel(alert_text, title="Alerts")
