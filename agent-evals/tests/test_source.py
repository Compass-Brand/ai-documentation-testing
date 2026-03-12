"""Tests for source-aware task and doc_tree loading."""

from __future__ import annotations

import json
import textwrap

from agent_evals.source import load_doc_tree_for_source, load_tasks_for_source


def _write_sample_task(task_dir, adapter_name):
    """Write a minimal valid task YAML into task_dir."""
    type_map = {
        "ambigqa": "disambiguation",
        "bigcodebench": "compositional",
        "code-rag-bench": "retrieval",
        "ds1000": "code_generation",
        "ibm-techqa": "fact_extraction",
        "multihop-rag": "multi_hop",
        "repliqa": "negative",
        "swe-bench": "agentic",
        "wikicontradict": "conflicting",
    }
    task_type = type_map.get(adapter_name, "retrieval")
    task_id = f"{task_type}_001"

    yaml_content = textwrap.dedent(f"""\
        task_id: {task_id}
        type: {task_type}
        question: "Sample question for {adapter_name}"
        domain: technical_qa
        difficulty: medium
        tags: []
        metadata:
          expected_answer: "sample answer"
          source_dataset: {adapter_name}
    """)
    (task_dir / f"{task_id}.yaml").write_text(yaml_content)


def _make_doc_tree_json(name):
    """Create a minimal valid DocTree JSON for an adapter."""
    return json.dumps({
        "files": {
            f"{name}_readme.md": {
                "rel_path": f"{name}_readme.md",
                "content": f"# {name} docs",
                "size_bytes": 50,
                "token_count": 100,
                "tier": "reference",
                "section": "Guides",
            }
        },
        "scanned_at": "2026-03-12T00:00:00+00:00",
        "source": name,
        "total_tokens": 100,
    })


class TestGoldStandardFromDatasets:
    def test_gold_standard_loads_from_prepared_datasets(self, tmp_path, monkeypatch):
        """gold_standard source loads HF datasets when prepared."""
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager(cache_dir=tmp_path)
        for name in mgr.required_adapters():
            task_dir = tmp_path / name / "tasks"
            task_dir.mkdir(parents=True)
            _write_sample_task(task_dir, name)
            marker = tmp_path / name / ".prepared"
            marker.write_text("task_count=1\n")

        original_init = GoldStandardManager.__init__

        def patched_init(self, cache_dir=None, limits=None):
            original_init(self, cache_dir=tmp_path, limits=limits)

        monkeypatch.setattr(GoldStandardManager, "__init__", patched_init)

        tasks = load_tasks_for_source("gold_standard")
        assert len(tasks) == 9  # one task per adapter

    def test_gold_standard_falls_back_to_legacy_when_not_prepared(
        self, tmp_path, monkeypatch
    ):
        """gold_standard falls back to legacy YAMLs when datasets not prepared."""
        from agent_evals.datasets.gold_standard import GoldStandardManager

        original_init = GoldStandardManager.__init__

        def patched_init(self, cache_dir=None, limits=None):
            original_init(self, cache_dir=tmp_path, limits=limits)

        monkeypatch.setattr(GoldStandardManager, "__init__", patched_init)

        tasks = load_tasks_for_source("gold_standard")
        assert len(tasks) > 0  # Legacy tasks loaded

    def test_legacy_source_loads_hand_crafted_yamls(self):
        """--source legacy explicitly loads old hand-crafted tasks."""
        tasks = load_tasks_for_source("legacy")
        assert len(tasks) > 0


class TestGoldStandardDocTree:
    def test_gold_standard_doc_tree_merges_adapters(self, tmp_path, monkeypatch):
        """gold_standard doc_tree merges all adapter doc trees."""
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager(cache_dir=tmp_path)
        for name in mgr.required_adapters():
            marker = tmp_path / name / ".prepared"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("task_count=1\n")
            dt_path = tmp_path / name / "doc_tree.json"
            dt_path.write_text(_make_doc_tree_json(name))

        original_init = GoldStandardManager.__init__

        def patched_init(self, cache_dir=None, limits=None):
            original_init(self, cache_dir=tmp_path, limits=limits)

        monkeypatch.setattr(GoldStandardManager, "__init__", patched_init)

        doc_tree = load_doc_tree_for_source("gold_standard")
        assert len(doc_tree.files) == 9
        assert any(key.startswith("ambigqa/") for key in doc_tree.files)

    def test_legacy_doc_tree_returns_sample(self):
        """--source legacy returns the built-in sample doc tree."""
        doc_tree = load_doc_tree_for_source("legacy")
        assert doc_tree is not None
        assert len(doc_tree.files) > 0
