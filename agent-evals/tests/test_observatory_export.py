"""Tests for observatory export/import functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_evals.cli import main
from agent_evals.observatory.export import export_run, import_run
from agent_evals.observatory.store import ObservatoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial_kwargs(
    run_id: str = "run_001",
    *,
    task_id: str = "task_1",
    task_type: str = "retrieval",
    variant_name: str = "flat",
    repetition: int = 1,
    score: float = 0.85,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
    cost: float | None = 0.001,
    latency_seconds: float = 1.5,
    model: str = "claude",
    source: str = "gold_standard",
    error: str | None = None,
) -> dict:
    """Build keyword args for record_trial."""
    return {
        "run_id": run_id,
        "task_id": task_id,
        "task_type": task_type,
        "variant_name": variant_name,
        "repetition": repetition,
        "score": score,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "latency_seconds": latency_seconds,
        "model": model,
        "source": source,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    """Create a fresh ObservatoryStore in a temp directory."""
    return ObservatoryStore(db_path=tmp_path / "observatory.db")


@pytest.fixture
def store_with_run(store: ObservatoryStore) -> ObservatoryStore:
    """Store with a run and one trial already created."""
    store.create_run("run_001", "taguchi", {"model": "claude"})
    store.record_trial(**_make_trial_kwargs())
    return store


# ---------------------------------------------------------------------------
# TestExportProducesValidJson
# ---------------------------------------------------------------------------


class TestExportProducesValidJson:
    """export_run should produce a well-structured JSON file."""

    def test_export_produces_valid_json(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        out = tmp_path / "export.json"
        export_run(store_with_run, "run_001", out)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))

        # Top-level structure
        assert data["format_version"] == 1
        assert "run" in data
        assert "trials" in data
        assert "phase_results" in data
        assert "factor_definitions" in data
        assert "report_artifacts" in data

        # Run metadata
        assert data["run"]["run_id"] == "run_001"
        assert data["run"]["run_type"] == "taguchi"

        # Trials
        assert len(data["trials"]) == 1
        assert data["trials"][0]["task_id"] == "task_1"

    def test_export_nonexistent_run_raises(
        self, store: ObservatoryStore, tmp_path: Path
    ) -> None:
        out = tmp_path / "export.json"
        with pytest.raises(ValueError, match="not found"):
            export_run(store, "nonexistent", out)


# ---------------------------------------------------------------------------
# TestRoundTripPreservesData
# ---------------------------------------------------------------------------


class TestRoundTripPreservesData:
    """Export then import should preserve all data."""

    def test_round_trip_preserves_data(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        # Add factor definitions
        store_with_run.save_factor_definitions(
            "run_001",
            [
                {
                    "factor_name": "heading_style",
                    "axis_id": 1,
                    "level_index": 0,
                    "level_name": "flat",
                    "description": "Flat headings",
                },
            ],
        )

        # Add report artifact
        store_with_run.save_report_artifact(
            "run_001",
            "summary",
            {"mean_score": 0.85, "trials": 1},
        )

        # Export from source
        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        # Import into fresh DB
        dest_store = ObservatoryStore(db_path=tmp_path / "dest.db")
        imported_id = import_run(dest_store, export_path)

        assert imported_id == "run_001"

        # Verify run metadata
        summary = dest_store.get_run_summary("run_001")
        assert summary.run_type == "taguchi"
        assert summary.config == {"model": "claude"}

        # Verify trials
        trials = dest_store.get_trials("run_001")
        assert len(trials) == 1
        assert trials[0].task_id == "task_1"
        assert trials[0].score == 0.85

        # Verify factor definitions
        factors = dest_store.get_factor_definitions("run_001")
        assert len(factors) == 1
        assert factors[0]["factor_name"] == "heading_style"

        # Verify report artifacts
        artifacts = dest_store.list_report_artifacts("run_001")
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "summary"
        artifact_data = dest_store.get_report_artifact("run_001", "summary")
        assert artifact_data is not None
        assert artifact_data["data"]["mean_score"] == 0.85

    def test_round_trip_preserves_phase_results(self, tmp_path: Path) -> None:
        """Phase results should survive export -> import round-trip."""
        src = ObservatoryStore(db_path=tmp_path / "src.db")
        src.create_run("run_001", "taguchi", {"model": "claude"})
        src.record_trial(
            run_id="run_001", task_id="t1", task_type="retrieval",
            variant_name="flat", repetition=1, score=0.85,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.001, latency_seconds=1.5, model="claude",
        )
        src.save_phase_results(
            run_id="run_001",
            main_effects={"structure": {"flat": 2.5, "nested": 1.8}},
            anova={"factors": [{"name": "structure", "p_value": 0.03}]},
            optimal={"structure": "flat"},
            significant_factors=["structure"],
            quality_type="larger_is_better",
            total_cost=5.50,
            total_tokens=250000,
            elapsed_seconds=1800.0,
        )

        export_path = tmp_path / "bundle.json"
        export_run(src, "run_001", export_path)

        dst = ObservatoryStore(db_path=tmp_path / "dst.db")
        import_run(dst, export_path)

        result = dst.get_phase_results("run_001")
        assert result is not None
        assert result["main_effects"] == {"structure": {"flat": 2.5, "nested": 1.8}}
        assert result["optimal"] == {"structure": "flat"}
        assert result["significant_factors"] == ["structure"]
        assert result["quality_type"] == "larger_is_better"
        assert result["total_cost"] == pytest.approx(5.50)
        assert result["total_tokens"] == 250000
        assert result["elapsed_seconds"] == pytest.approx(1800.0)


# ---------------------------------------------------------------------------
# TestImportRejectsDuplicateRun
# ---------------------------------------------------------------------------


class TestImportRejectsDuplicateRun:
    """import_run should reject a run_id that already exists."""

    def test_import_rejects_duplicate_run(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        # Import into same DB should fail
        with pytest.raises(ValueError, match="already exists"):
            import_run(store_with_run, export_path)


# ---------------------------------------------------------------------------
# TestImportWithForceReplaces
# ---------------------------------------------------------------------------


class TestImportWithForceReplaces:
    """import_run with force=True should delete existing and re-import."""

    def test_import_with_force_replaces(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        # Force import into same DB should succeed
        imported_id = import_run(store_with_run, export_path, force=True)
        assert imported_id == "run_001"

        # Data should be intact
        summary = store_with_run.get_run_summary("run_001")
        assert summary.run_type == "taguchi"

        trials = store_with_run.get_trials("run_001")
        assert len(trials) == 1


# ---------------------------------------------------------------------------
# TestExportIncludesTraces
# ---------------------------------------------------------------------------


class TestExportIncludesTraces:
    """export_run should include trace data when traces exist."""

    def test_export_includes_traces(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        # Get the trial_id from the existing trial
        trials = store_with_run.get_trials("run_001")
        trial_id = trials[0].trial_id

        # Add a trace
        store_with_run.record_trace(
            trial_id=trial_id,
            prompt_json=[{"role": "user", "content": "test prompt"}],
            response_text="test response",
        )

        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        data = json.loads(export_path.read_text(encoding="utf-8"))

        # Verify traces are in the bundle
        assert "traces" in data
        assert len(data["traces"]) == 1
        trace = data["traces"][0]
        assert trace["trial_id"] == trial_id
        assert trace["prompt_json"] == [{"role": "user", "content": "test prompt"}]
        assert trace["response_text"] == "test response"

    def test_round_trip_preserves_traces(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        trials = store_with_run.get_trials("run_001")
        trial_id = trials[0].trial_id

        store_with_run.record_trace(
            trial_id=trial_id,
            prompt_json=[{"role": "user", "content": "test prompt"}],
            response_text="test response",
        )

        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        dest_store = ObservatoryStore(db_path=tmp_path / "dest.db")
        import_run(dest_store, export_path)

        # Traces reference the original trial_id which may differ in the dest DB.
        # But the trial should be present and the trace should be attached.
        dest_trials = dest_store.get_trials("run_001")
        assert len(dest_trials) == 1
        dest_trace = dest_store.get_trace(dest_trials[0].trial_id)
        assert dest_trace is not None
        assert dest_trace["prompt_json"] == [
            {"role": "user", "content": "test prompt"}
        ]
        assert dest_trace["response_text"] == "test response"


# ---------------------------------------------------------------------------
# TestExportIncludesCallDetails
# ---------------------------------------------------------------------------


class TestExportIncludesCallDetails:
    """export_run should include LLM call details when they exist."""

    def test_export_includes_call_details(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        trials = store_with_run.get_trials("run_001")
        trial_id = trials[0].trial_id

        store_with_run.save_llm_call_details(
            trial_id,
            [
                {
                    "call_index": 0,
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0.001,
                    "api_call_ms": 500.0,
                    "cached_tokens": 0,
                    "model": "claude",
                    "provider": "openrouter",
                },
            ],
        )

        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        data = json.loads(export_path.read_text(encoding="utf-8"))

        assert "call_details" in data
        assert len(data["call_details"]) == 1
        detail = data["call_details"][0]
        assert detail["trial_id"] == trial_id
        assert len(detail["calls"]) == 1
        assert detail["calls"][0]["call_index"] == 0
        assert detail["calls"][0]["model"] == "claude"

    def test_round_trip_preserves_call_details(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        trials = store_with_run.get_trials("run_001")
        trial_id = trials[0].trial_id

        store_with_run.save_llm_call_details(
            trial_id,
            [
                {
                    "call_index": 0,
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0.001,
                    "api_call_ms": 500.0,
                    "cached_tokens": 0,
                    "model": "claude",
                    "provider": "openrouter",
                },
            ],
        )

        export_path = tmp_path / "export.json"
        export_run(store_with_run, "run_001", export_path)

        dest_store = ObservatoryStore(db_path=tmp_path / "dest.db")
        import_run(dest_store, export_path)

        dest_trials = dest_store.get_trials("run_001")
        assert len(dest_trials) == 1
        calls = dest_store.get_llm_call_details(dest_trials[0].trial_id)
        assert len(calls) == 1
        assert calls[0]["call_index"] == 0
        assert calls[0]["model"] == "claude"
        assert calls[0]["provider"] == "openrouter"


# ---------------------------------------------------------------------------
# TestCLIExportImport
# ---------------------------------------------------------------------------


class TestCLIExportImport:
    """CLI export and import subcommands."""

    def test_cli_export_produces_file(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "observatory.db"
        out_path = tmp_path / "cli_export.json"

        result = main([
            "export", "run_001",
            "-o", str(out_path),
            "--db", str(db_path),
        ])

        assert result == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["run"]["run_id"] == "run_001"

    def test_cli_import_loads_bundle(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "cli_export.json"
        export_run(store_with_run, "run_001", export_path)

        # Import into a different DB
        dest_db = tmp_path / "dest.db"
        result = main([
            "import", str(export_path),
            "--db", str(dest_db),
        ])

        assert result == 0
        dest_store = ObservatoryStore(db_path=dest_db)
        summary = dest_store.get_run_summary("run_001")
        assert summary.run_type == "taguchi"

    def test_cli_export_missing_run_returns_1(self, tmp_path: Path) -> None:
        db_path = tmp_path / "observatory.db"
        # Create empty DB
        ObservatoryStore(db_path=db_path)
        out_path = tmp_path / "out.json"

        result = main([
            "export", "nonexistent",
            "-o", str(out_path),
            "--db", str(db_path),
        ])
        assert result == 1

    def test_cli_import_missing_file_returns_1(self, tmp_path: Path) -> None:
        result = main([
            "import", str(tmp_path / "does_not_exist.json"),
            "--db", str(tmp_path / "dest.db"),
        ])
        assert result == 1

    def test_cli_import_with_force(
        self, store_with_run: ObservatoryStore, tmp_path: Path
    ) -> None:
        export_path = tmp_path / "cli_export.json"
        export_run(store_with_run, "run_001", export_path)

        # Import into same DB with --force
        result = main([
            "import", str(export_path),
            "--db", str(tmp_path / "observatory.db"),
            "--force",
        ])

        assert result == 0
