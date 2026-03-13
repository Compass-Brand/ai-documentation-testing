"""Stratified train/test splitting for evaluation tasks."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.tasks.base import EvalTask


def stratified_split(
    tasks: list[EvalTask],
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[EvalTask], list[EvalTask]]:
    """Split tasks into train and test sets, stratified by task type.

    Ensures each task type is represented proportionally in both sets.
    Types with fewer than 2 tasks are placed entirely in train.

    Args:
        tasks: All evaluation tasks to split.
        train_ratio: Fraction of tasks for training (0.0-1.0).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (train_tasks, test_tasks).
    """
    if not tasks:
        return [], []

    rng = random.Random(seed)

    # Group by task type
    by_type: dict[str, list[EvalTask]] = defaultdict(list)
    for task in tasks:
        by_type[task.definition.type].append(task)

    train: list[EvalTask] = []
    test: list[EvalTask] = []

    for task_type in sorted(by_type):
        group = by_type[task_type]
        rng.shuffle(group)

        if len(group) < 2:
            train.extend(group)
            continue

        split_idx = max(1, round(len(group) * train_ratio))
        # Ensure at least 1 in test
        split_idx = min(split_idx, len(group) - 1)
        train.extend(group[:split_idx])
        test.extend(group[split_idx:])

    return train, test
