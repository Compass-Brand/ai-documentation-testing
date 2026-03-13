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


class TestAllAdapters:
    def test_returns_eleven_adapters(self):
        """all_adapters() returns 9 HF + 2 synthetic = 11."""
        mgr = GoldStandardManager()
        adapters = mgr.all_adapters()
        assert len(adapters) == 11

    def test_includes_synthetic_adapters(self):
        """all_adapters() includes perturbation and synthetic-efficiency."""
        mgr = GoldStandardManager()
        adapters = mgr.all_adapters()
        assert "perturbation" in adapters
        assert "synthetic-efficiency" in adapters

    def test_is_superset_of_required(self):
        """all_adapters() contains all required_adapters()."""
        mgr = GoldStandardManager()
        required = set(mgr.required_adapters())
        all_names = set(mgr.all_adapters())
        assert required.issubset(all_names)


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


class TestPrepareAllErrorResilience:
    """prepare_all() should continue when individual adapters fail."""

    def test_continues_after_adapter_failure(self, tmp_path, monkeypatch):
        """If one adapter raises, others still prepare."""
        from agent_evals.datasets import gold_standard as gs_mod

        call_log: list[str] = []

        class FakeAdapter:
            def __init__(self, name, *, should_fail=False):
                self._name = name
                self._should_fail = should_fail

            def convert_tasks(self, output_dir, limit=None, **kw):
                call_log.append(self._name)
                if self._should_fail:
                    raise RuntimeError(f"Simulated failure for {self._name}")
                return 1

            def build_doc_tree(self, limit=None):
                from unittest.mock import MagicMock

                mock_dt = MagicMock()
                mock_dt.model_dump_json.return_value = '{"files":{},"scanned_at":"2026-01-01T00:00:00+00:00","source":"x","total_tokens":0}'
                return mock_dt

        # Make ds1000 fail, others succeed
        adapters = {}
        for name in gs_mod._REQUIRED_ADAPTERS:
            adapters[name] = FakeAdapter(name, should_fail=(name == "ds1000"))

        def mock_get_adapter(name):
            return adapters.get(name, FakeAdapter(name))

        monkeypatch.setattr(gs_mod, "get_adapter", mock_get_adapter)
        monkeypatch.setattr(gs_mod, "load_all", lambda: None)

        mgr = GoldStandardManager(cache_dir=tmp_path)
        results = mgr.prepare_all()

        # ds1000 should not be in results (it failed)
        assert "ds1000" not in results
        # All other 8 adapters should have succeeded
        succeeded = [n for n in gs_mod._REQUIRED_ADAPTERS if n != "ds1000"]
        for name in succeeded:
            assert name in results, f"{name} should have succeeded"
            assert results[name] == 1

    def test_logs_warning_on_adapter_failure(self, tmp_path, monkeypatch, caplog):
        """Failed adapters should produce a warning log."""
        import logging

        from agent_evals.datasets import gold_standard as gs_mod

        class FailingAdapter:
            def convert_tasks(self, output_dir, limit=None, **kw):
                raise RuntimeError("Download failed")

        monkeypatch.setattr(
            gs_mod, "get_adapter", lambda name: FailingAdapter(),
        )
        monkeypatch.setattr(gs_mod, "load_all", lambda: None)

        mgr = GoldStandardManager(cache_dir=tmp_path)
        with caplog.at_level(logging.WARNING):
            mgr.prepare_all()

        assert any("ambigqa" in r.message for r in caplog.records)
        assert any("Download failed" in r.message for r in caplog.records)


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

    def test_generates_perturbation_from_ibm_techqa(self, tmp_path):
        """Perturbation tasks auto-generate from prepared ibm-techqa data."""
        self._setup_prepared_adapter(tmp_path, "ibm-techqa", [
            {
                "task_id": "ibmtechqa_fact_extraction_001",
                "type": "fact_extraction",
                "question": "How do you configure logging in Flask?",
                "domain": "technical_qa",
                "difficulty": "medium",
                "tags": ["technical"],
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
