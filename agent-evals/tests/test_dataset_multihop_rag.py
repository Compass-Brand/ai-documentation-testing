"""Tests for the MultiHop-RAG dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


def _make_multihop_record(
    query_id: str = "q001",
    query: str = "What happened after X and how did Y respond?",
    answer: str = "X caused Z, and Y responded with W.",
    question_type: str = "inference_query",
    evidence_list: list[dict] | None = None,
) -> dict:
    if evidence_list is None:
        evidence_list = [
            {"fact": "X happened in January.", "source": "article_001"},
            {"fact": "Y responded in February.", "source": "article_002"},
        ]
    return {
        "query_id": query_id,
        "query": query,
        "answer": answer,
        "question_type": question_type,
        "evidence_list": evidence_list,
    }


def _make_corpus_record(
    doc_id: str = "article_001",
    title: str = "Breaking: X Happens",
    content: str = "In January, X happened due to several factors...",
) -> dict:
    return {"doc_id": doc_id, "title": title, "content": content}


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.filter = lambda fn: _mock_dataset([r for r in records if fn(r)])
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestMultiHopRAGMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        assert MultiHopRAGAdapter().name() == "multihop-rag"

    def test_task_type(self) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        assert MultiHopRAGAdapter().task_type() == "multi_hop"

    def test_domain(self) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        assert MultiHopRAGAdapter().domain() == "news_articles"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        assert MultiHopRAGAdapter().contamination_risk() == "moderate"


class TestMultiHopRAGConvertTasks:
    def test_converts_records_to_multi_hop_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        records = [
            _make_multihop_record(query_id="q001"),
            _make_multihop_record(query_id="q002"),
        ]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        records = [
            _make_multihop_record(
                query_id="q001",
                query="What happened after X?",
                answer="X caused Z.",
                evidence_list=[
                    {"fact": "X happened.", "source": "art1"},
                    {"fact": "Z resulted.", "source": "art2"},
                ],
            ),
        ]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("multihoprag_multi_hop_")
        assert task["type"] == "multi_hop"
        assert task["domain"] == "news_articles"
        assert "reasoning_chain" in task["metadata"]
        assert "question_decomposition" in task["metadata"]
        assert isinstance(task["metadata"]["reasoning_chain"], list)

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        records = [_make_multihop_record(query_id=f"q{i:03d}") for i in range(20)]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5


class TestMultiHopRAGBuildDocTree:
    def test_builds_doc_tree(self) -> None:
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        records = [
            _make_multihop_record(
                evidence_list=[
                    {"fact": "Fact 1.", "source": "art1"},
                    {"fact": "Fact 2.", "source": "art2"},
                ],
            ),
        ]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) >= 1


class TestMultiHopRAGEmptyReasoningChain:
    """Bug #177: records with empty reasoning_chain cause scorer to return 1.0."""

    def test_skips_records_with_empty_evidence_list(self, tmp_path: Path) -> None:
        """Records with empty evidence_list should be filtered out."""
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        empty_evidence = _make_multihop_record(
            query_id="e1", evidence_list=[],
        )
        valid_record = _make_multihop_record(query_id="v1")

        records = [empty_evidence, valid_record]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 1
        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert len(task["metadata"]["reasoning_chain"]) >= 1

    def test_skips_records_with_factless_evidence(self, tmp_path: Path) -> None:
        """Records where all evidence entries have empty facts should be filtered."""
        from agent_evals.datasets.multihop_rag import MultiHopRAGAdapter

        no_facts = _make_multihop_record(
            query_id="nf1",
            evidence_list=[
                {"fact": "", "source": "art1"},
                {"fact": "", "source": "art2"},
            ],
        )
        records = [no_facts]
        adapter = MultiHopRAGAdapter()
        with patch(
            "agent_evals.datasets.multihop_rag.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 0


class TestMultiHopRAGRegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.multihop_rag  # noqa: F401

        assert "multihop-rag" in DATASET_REGISTRY
