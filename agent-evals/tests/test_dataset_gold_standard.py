"""Tests for the gold standard dataset manager."""

from __future__ import annotations

import pytest

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
