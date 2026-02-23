"""Perturbation dataset adapter for robustness tasks.

Generates perturbed variants of existing tasks by applying
character-level, word-level, and semantic perturbations.
Does not use HuggingFace datasets directly.

Contamination risk: LOW (generated from source tasks)
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets.base import DatasetAdapter

# Simple perturbation functions (no external dependencies)
_PERTURBATION_TYPES = [
    "typo",
    "char_swap",
    "char_delete",
    "word_swap",
    "case_change",
]


def _apply_typo(text: str) -> str:
    """Swap two adjacent characters in a random word."""
    words = text.split()
    if len(words) < 2:
        return text
    idx = random.randint(0, len(words) - 1)
    word = words[idx]
    if len(word) > 2:
        pos = random.randint(0, len(word) - 2)
        word = word[:pos] + word[pos + 1] + word[pos] + word[pos + 2:]
        words[idx] = word
    return " ".join(words)


def _apply_perturbation(text: str, ptype: str) -> str:
    """Apply a simple perturbation to text."""
    if ptype == "typo":
        return _apply_typo(text)
    if ptype == "char_swap":
        return _apply_typo(text)  # Similar effect
    if ptype == "char_delete":
        words = text.split()
        if words:
            idx = random.randint(0, len(words) - 1)
            word = words[idx]
            if len(word) > 2:
                pos = random.randint(1, len(word) - 1)
                words[idx] = word[:pos] + word[pos + 1:]
            return " ".join(words)
        return text
    if ptype == "word_swap":
        words = text.split()
        if len(words) > 2:
            i, j = random.sample(range(len(words)), 2)
            words[i], words[j] = words[j], words[i]
        return " ".join(words)
    if ptype == "case_change":
        words = text.split()
        if words:
            idx = random.randint(0, len(words) - 1)
            words[idx] = words[idx].upper() if words[idx].islower() else words[idx].lower()
        return " ".join(words)
    return text


@register_dataset
class PerturbationAdapter(DatasetAdapter):
    """Generator adapter that creates robustness tasks from source tasks."""

    def name(self) -> str:
        return "perturbation"

    def hf_dataset_id(self) -> str | None:
        return None  # Not a HuggingFace dataset

    def task_type(self) -> str:
        return "robustness"

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
        """Generate perturbed robustness tasks from source YAML tasks."""
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

            original_question = source_task["question"]
            source_meta = source_task.get("metadata", {})

            ptype = _PERTURBATION_TYPES[count % len(_PERTURBATION_TYPES)]
            perturbed = _apply_perturbation(original_question, ptype)

            task_id = self._generate_task_id("robustness", count)
            task = {
                "task_id": task_id,
                "type": "robustness",
                "question": perturbed,
                "domain": source_task.get("domain", self.domain()),
                "difficulty": source_task.get("difficulty", "medium"),
                "tags": ["robustness", ptype],
                "metadata": {
                    "expected_answer": source_meta.get("expected_answer", ""),
                    "answer_aliases": source_meta.get("answer_aliases", []),
                    "base_task_id": source_task.get("task_id", ""),
                    "perturbation_type": ptype,
                    "original_question": original_question,
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
        """Perturbation adapter uses the source dataset's DocTree."""
        from agent_index.models import DocTree

        return DocTree(
            files={},
            scanned_at=datetime.now(tz=UTC),
            source="perturbation-generator",
            total_tokens=0,
        )
