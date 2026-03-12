"""Tests for the gold standard dataset manager."""

from __future__ import annotations

from agent_evals.datasets.gold_standard import GoldStandardManager


class TestRequiredAdapters:
    def test_returns_nine_adapters(self):
        """All 9 HF adapters are required for gold standard."""
        mgr = GoldStandardManager()
        adapters = mgr.required_adapters()
        assert len(adapters) == 9

    def test_includes_key_adapters(self):
        """Key adapters like ds1000 and ibm-techqa are included."""
        mgr = GoldStandardManager()
        adapters = mgr.required_adapters()
        assert "ds1000" in adapters
        assert "ibm-techqa" in adapters
        assert "ambigqa" in adapters
        assert "repliqa" in adapters


class TestIsPrepared:
    def test_false_when_no_datasets_exist(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        assert mgr.is_prepared() is False

    def test_true_when_all_present(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        for name in mgr.required_adapters():
            marker = tmp_path / name / ".prepared"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                "task_count=10\nprepared_at=2026-03-12T00:00:00+00:00\n"
            )
        assert mgr.is_prepared() is True

    def test_false_when_partially_prepared(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        # Only prepare first 3
        for name in list(mgr.required_adapters())[:3]:
            marker = tmp_path / name / ".prepared"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("task_count=5\n")
        assert mgr.is_prepared() is False


class TestMissingAdapters:
    def test_all_missing_initially(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        missing = mgr.missing_adapters()
        assert len(missing) == 9

    def test_excludes_prepared(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        marker = tmp_path / "ds1000" / ".prepared"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("task_count=10\n")
        missing = mgr.missing_adapters()
        assert "ds1000" not in missing
        assert len(missing) == 8


class TestLimitFor:
    def test_ibm_techqa_has_default_limit(self):
        mgr = GoldStandardManager()
        assert mgr.limit_for("ibm-techqa") == 50

    def test_other_adapters_use_general_default(self):
        mgr = GoldStandardManager()
        assert mgr.limit_for("ds1000") == 100

    def test_custom_limits_override(self):
        mgr = GoldStandardManager(limits={"ds1000": 25})
        assert mgr.limit_for("ds1000") == 25
        # ibm-techqa still uses its built-in default
        assert mgr.limit_for("ibm-techqa") == 50

    def test_custom_limit_overrides_default(self):
        mgr = GoldStandardManager(limits={"ibm-techqa": 200})
        assert mgr.limit_for("ibm-techqa") == 200


class TestGenerateSyntheticTasks:
    """Tests for _generate_synthetic_tasks wiring in GoldStandardManager."""

    def _setup_prepared_adapter(self, cache_dir, adapter_name, tasks):
        """Mark an adapter as prepared and write sample task YAMLs."""
        import yaml

        task_dir = cache_dir / adapter_name / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        for task_data in tasks:
            path = task_dir / f"{task_data['task_id']}.yaml"
            path.write_text(
                yaml.dump(task_data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        marker = cache_dir / adapter_name / ".prepared"
        marker.write_text(f"task_count={len(tasks)}\n")

    def test_generates_efficiency_from_ibm_techqa(self, tmp_path):
        """Efficiency tasks auto-generate from prepared ibm-techqa data."""
        self._setup_prepared_adapter(tmp_path, "ibm-techqa", [
            {
                "task_id": "ibmtechqa_fact_extraction_001",
                "type": "fact_extraction",
                "question": "What is the default connection timeout?",
                "domain": "technical_qa",
                "difficulty": "medium",
                "tags": ["fact_extraction"],
                "metadata": {
                    "expected_answer": "30 seconds",
                    "answer_aliases": ["30s"],
                },
            },
        ])
        mgr = GoldStandardManager(cache_dir=tmp_path)
        results = mgr._generate_synthetic_tasks(limit=10)
        assert "synthetic-efficiency" in results
        assert results["synthetic-efficiency"] >= 1

        # Verify task files were written
        eff_tasks = list((tmp_path / "synthetic-efficiency" / "tasks").glob("*.yaml"))
        assert len(eff_tasks) >= 1

    def test_generates_perturbation_from_code_rag_bench(self, tmp_path):
        """Perturbation tasks auto-generate from prepared code-rag-bench data."""
        self._setup_prepared_adapter(tmp_path, "code-rag-bench", [
            {
                "task_id": "coderagbench_retrieval_001",
                "type": "retrieval",
                "question": "How do you configure logging in Flask?",
                "domain": "library_docs",
                "difficulty": "medium",
                "tags": ["retrieval"],
                "metadata": {
                    "expected_answer": "Use app.logger",
                    "answer_aliases": [],
                },
            },
        ])
        mgr = GoldStandardManager(cache_dir=tmp_path)
        results = mgr._generate_synthetic_tasks(limit=10)
        assert "perturbation" in results
        assert results["perturbation"] >= 1

        # Verify task files were written
        perturb_tasks = list((tmp_path / "perturbation" / "tasks").glob("*.yaml"))
        assert len(perturb_tasks) >= 1

    def test_skips_synthetic_when_source_not_prepared(self, tmp_path):
        """No synthetic tasks generated if source adapters aren't prepared."""
        mgr = GoldStandardManager(cache_dir=tmp_path)
        results = mgr._generate_synthetic_tasks(limit=10)
        assert results == {}

    def test_marks_synthetic_as_prepared(self, tmp_path):
        """Synthetic adapters get .prepared markers after generation."""
        self._setup_prepared_adapter(tmp_path, "ibm-techqa", [
            {
                "task_id": "ibmtechqa_fact_extraction_001",
                "type": "fact_extraction",
                "question": "What is X?",
                "domain": "technical_qa",
                "difficulty": "easy",
                "tags": ["fact_extraction"],
                "metadata": {"expected_answer": "Y", "answer_aliases": []},
            },
        ])
        mgr = GoldStandardManager(cache_dir=tmp_path)
        mgr._generate_synthetic_tasks(limit=10)
        assert mgr._cache.is_prepared("synthetic-efficiency")
