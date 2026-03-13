"""Tests for train/test split module."""

from __future__ import annotations

import pytest

from agent_evals.splits import stratified_split
from agent_evals.tasks.base import TaskDefinition
from agent_evals.tasks.retrieval import RetrievalTask
from agent_evals.tasks.code_generation import CodeGenerationTask
from agent_evals.tasks.fact_extraction import FactExtractionTask


@pytest.fixture
def sample_tasks():
    """Create a diverse set of tasks for split testing."""
    tasks = []
    for i in range(1, 11):
        tasks.append(RetrievalTask(TaskDefinition(
            task_id=f"retrieval_{i:03d}",
            type="retrieval",
            question=f"Retrieve info {i}",
            domain="framework_api",
            difficulty="easy",
        )))
    for i in range(1, 8):
        tasks.append(CodeGenerationTask(TaskDefinition(
            task_id=f"code_generation_{i:03d}",
            type="code_generation",
            question=f"Generate code {i}",
            domain="framework_api",
            difficulty="medium",
        )))
    for i in range(1, 6):
        tasks.append(FactExtractionTask(TaskDefinition(
            task_id=f"fact_extraction_{i:03d}",
            type="fact_extraction",
            question=f"Extract fact {i}",
            domain="framework_api",
            difficulty="hard",
        )))
    return tasks


class TestStratifiedSplit:
    """Tests for stratified_split function."""

    def test_split_preserves_total_count(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        assert len(train) + len(test) == len(sample_tasks)

    def test_split_ratio_approximately_correct(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.7, seed=42)
        ratio = len(train) / len(sample_tasks)
        assert 0.6 <= ratio <= 0.8  # Allow slack for stratification rounding

    def test_split_preserves_task_type_distribution(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train_types = {t.definition.type for t in train}
        test_types = {t.definition.type for t in test}
        all_types = {t.definition.type for t in sample_tasks}
        # Every type with 2+ tasks should appear in both splits
        for task_type in all_types:
            type_count = sum(1 for t in sample_tasks if t.definition.type == task_type)
            if type_count >= 2:
                assert task_type in train_types, f"{task_type} missing from train"
                assert task_type in test_types, f"{task_type} missing from test"

    def test_split_deterministic_with_same_seed(self, sample_tasks):
        train1, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train2, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        assert [t.definition.task_id for t in train1] == [t.definition.task_id for t in train2]

    def test_split_different_with_different_seed(self, sample_tasks):
        train1, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train2, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=99)
        ids1 = {t.definition.task_id for t in train1}
        ids2 = {t.definition.task_id for t in train2}
        assert ids1 != ids2

    def test_split_no_overlap(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train_ids = {t.definition.task_id for t in train}
        test_ids = {t.definition.task_id for t in test}
        assert train_ids.isdisjoint(test_ids)

    def test_empty_task_list(self):
        train, test = stratified_split([], train_ratio=0.8, seed=42)
        assert train == []
        assert test == []

    def test_single_task_goes_to_train(self):
        """Types with only 1 task go to train set."""
        tasks = [
            RetrievalTask(TaskDefinition(
                task_id="retrieval_001",
                type="retrieval",
                question="Q1",
                domain="framework_api",
                difficulty="easy",
            ))
        ]
        train, test = stratified_split(tasks, train_ratio=0.8, seed=42)
        assert len(train) == 1
        assert len(test) == 0
