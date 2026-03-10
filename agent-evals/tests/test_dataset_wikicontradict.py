"""Tests for the WikiContradict dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml


def _make_wikicontradict_record(
    id: int = 1,
    context1: str = "The river is approximately 500km long according to surveys.",
    context2: str = "Recent measurements show the river spans about 300km.",
    answer1: str = "The river is 500km long.",
    answer2: str = "The river spans 300km.",
    article_title: str = "Amazon River",
    question: str = "How long is the river?",
    contradict_type: str = "Explicit",
    ref_answer: str = "500km",
) -> dict:
    return {
        "context1": context1,
        "context2": context2,
        "answer1": answer1,
        "answer2": answer2,
        "WikipediaArticleTitle": article_title,
        "question": question,
        "contradictType": contradict_type,
        "ref_answer": ref_answer,
        "merged_context": f"{context1} {context2}",
        "url": f"https://en.wikipedia.org/wiki/{article_title.replace(' ', '_')}",
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestWikiContradictMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter
        assert WikiContradictAdapter().name() == "wikicontradict"

    def test_task_type(self) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter
        assert WikiContradictAdapter().task_type() == "conflicting"

    def test_domain(self) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter
        assert WikiContradictAdapter().domain() == "general_knowledge"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter
        assert WikiContradictAdapter().contamination_risk() == "high"


class TestWikiContradictConvertTasks:
    def test_converts_records_to_conflicting_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter

        records = [_make_wikicontradict_record(), _make_wikicontradict_record(id=2)]
        adapter = WikiContradictAdapter()
        with patch(
            "agent_evals.datasets.wikicontradict.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)
        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter

        records = [_make_wikicontradict_record()]
        adapter = WikiContradictAdapter()
        with patch(
            "agent_evals.datasets.wikicontradict.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert task["type"] == "conflicting"
        assert task["domain"] == "general_knowledge"
        assert "sources" in task["metadata"]
        assert "expected_resolution" in task["metadata"]
        assert isinstance(task["metadata"]["sources"], list)
        assert len(task["metadata"]["sources"]) == 2

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.wikicontradict import WikiContradictAdapter

        records = [_make_wikicontradict_record(id=i) for i in range(20)]
        adapter = WikiContradictAdapter()
        with patch(
            "agent_evals.datasets.wikicontradict.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)
        assert count == 5


class TestWikiContradictRegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY
        import agent_evals.datasets.wikicontradict  # noqa: F401
        assert "wikicontradict" in DATASET_REGISTRY
