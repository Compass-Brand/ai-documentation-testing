"""Synthetic Efficiency dataset adapter for efficiency tasks.

Generates token-budget-constrained tasks from existing source tasks.
Uses methodology from "Reasoning in Token Economies" (EMNLP 2024).

Contamination risk: LOW (generated from source tasks)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets.base import DatasetAdapter

# Budget tiers: (name, multiplier of ideal token count)
_BUDGET_TIERS = [
    ("tight", 0.5),
    ("moderate", 1.0),
    ("generous", 2.0),
]


@register_dataset
class SyntheticEfficiencyAdapter(DatasetAdapter):
    """Generator adapter that creates efficiency tasks with token budgets."""

    def name(self) -> str:
        return "synthetic-efficiency"

    def hf_dataset_id(self) -> str | None:
        return None  # Not a HuggingFace dataset

    def task_type(self) -> str:
        return "efficiency"

    def domain(self) -> str:
        return "framework_api"  # Inherited from source

    def license(self) -> str:
        return "same-as-source"

    def contamination_risk(self) -> str:
        return "low"

    def convert_tasks(
        self,
        output_dir: Path,
        limit: int | None = None,
        source_dir: Path | None = None,
        **kwargs: Any,
    ) -> int:
        """Generate efficiency tasks with token budgets from source tasks."""
        if source_dir is None:
            return 0

        source_files = sorted(source_dir.glob("*.yaml"))
        if not source_files:
            return 0

        count = 0
        for source_file in source_files:
            if limit is not None and count >= limit:
                break

            source_task = yaml.safe_load(source_file.read_text(encoding="utf-8"))
            if not source_task or "question" not in source_task:
                continue

            source_meta = source_task.get("metadata", {})
            expected = source_meta.get("expected_answer", "")

            # Estimate ideal token count from expected answer length
            ideal_tokens = max(len(expected.split()) * 2, 10)

            tier_name, multiplier = _BUDGET_TIERS[count % len(_BUDGET_TIERS)]
            token_budget = max(int(ideal_tokens * multiplier), 5)

            task_id = self._generate_task_id("efficiency", count)
            task = {
                "task_id": task_id,
                "type": "efficiency",
                "question": source_task["question"],
                "domain": source_task.get("domain", self.domain()),
                "difficulty": source_task.get("difficulty", "medium"),
                "tags": ["efficiency", tier_name],
                "metadata": {
                    "expected_answer": expected,
                    "answer_aliases": source_meta.get("answer_aliases", []),
                    "token_budget": token_budget,
                    "ideal_token_usage": ideal_tokens,
                    "budget_tier": tier_name,
                },
            }
            out_file = output_dir / f"{task_id}.yaml"
            out_file.write_text(
                yaml.dump(task, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            count += 1

        return count

    def build_doc_tree(self, limit: int | None = None) -> "DocTree":
        """Efficiency adapter uses the source dataset's DocTree."""
        from agent_index.models import DocTree

        return DocTree(
            files={},
            scanned_at=datetime.now(tz=UTC),
            source="synthetic-efficiency-generator",
            total_tokens=0,
        )
