"""Tests for the Synthetic Efficiency dataset adapter (generator)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _make_source_task_yaml(
    task_id: str = "fact_extraction_001",
    question: str = "What is the default TTL?",
    expected_answer: str = "300 seconds",
) -> str:
    return yaml.dump({
        "task_id": task_id,
        "type": "fact_extraction",
        "question": question,
        "domain": "framework_api",
        "difficulty": "easy",
        "tags": ["caching"],
        "metadata": {
            "expected_answer": expected_answer,
            "answer_aliases": ["300", "5 minutes"],
            "source_location": "api/caching.md",
        },
    }, default_flow_style=False)


class TestEfficiencyMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter
        assert SyntheticEfficiencyAdapter().name() == "synthetic-efficiency"

    def test_task_type(self) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter
        assert SyntheticEfficiencyAdapter().task_type() == "efficiency"

    def test_hf_dataset_id_is_none(self) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter
        assert SyntheticEfficiencyAdapter().hf_dataset_id() is None

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter
        assert SyntheticEfficiencyAdapter().contamination_risk() == "low"


class TestEfficiencyConvertTasks:
    def test_generates_efficiency_tasks_from_source(self, tmp_path: Path) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "task_001.yaml").write_text(
            _make_source_task_yaml("fact_extraction_001", "What is the default TTL?"),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        adapter = SyntheticEfficiencyAdapter()
        count = adapter.convert_tasks(output_dir, source_dir=source_dir)

        assert count >= 1

    def test_generated_yaml_has_efficiency_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "task_001.yaml").write_text(
            _make_source_task_yaml("fact_extraction_001", "What is the default TTL?"),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        adapter = SyntheticEfficiencyAdapter()
        adapter.convert_tasks(output_dir, source_dir=source_dir)

        yaml_files = list(output_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["type"] == "efficiency"
        assert "expected_answer" in task["metadata"]
        assert "token_budget" in task["metadata"]
        assert isinstance(task["metadata"]["token_budget"], int)

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.synthetic_efficiency import SyntheticEfficiencyAdapter

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        for i in range(5):
            (source_dir / f"task_{i:03d}.yaml").write_text(
                _make_source_task_yaml(f"fact_extraction_{i:03d}", f"Question {i}?"),
                encoding="utf-8",
            )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        adapter = SyntheticEfficiencyAdapter()
        count = adapter.convert_tasks(output_dir, source_dir=source_dir, limit=3)

        assert count <= 3


class TestEfficiencyRegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY
        import agent_evals.datasets.synthetic_efficiency  # noqa: F401
        assert "synthetic-efficiency" in DATASET_REGISTRY
