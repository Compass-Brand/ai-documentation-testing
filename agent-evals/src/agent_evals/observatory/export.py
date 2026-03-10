"""Export and import observatory runs as self-contained JSON bundles.

Provides round-trip serialisation of a complete experiment (run metadata,
trials, traces, LLM call details, phase results, factor definitions, and
report artifacts) for reproducibility and sharing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from agent_evals.observatory.store import ObservatoryStore

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1


def export_run(
    store: ObservatoryStore,
    run_id: str,
    path: Path,
) -> None:
    """Export a run and all associated data to a JSON file.

    Args:
        store: Source observatory store.
        run_id: Run to export.
        path: Output file path.

    Raises:
        ValueError: If the run_id does not exist.
    """
    # Run metadata (raises ValueError if not found)
    summary = store.get_run_summary(run_id)

    # Trials
    trials = store.get_trials(run_id)
    trials_data = [asdict(t) for t in trials]

    # Traces (keyed by trial_id)
    traces: list[dict] = []
    for trial in trials:
        trace = store.get_trace(trial.trial_id)
        if trace is not None:
            traces.append(
                {
                    "trial_id": trial.trial_id,
                    "prompt_json": trace["prompt_json"],
                    "response_text": trace["response_text"],
                    "created_at": trace["created_at"],
                }
            )

    # LLM call details (keyed by trial_id)
    call_details: list[dict] = []
    for trial in trials:
        calls = store.get_llm_call_details(trial.trial_id)
        if calls:
            call_details.append(
                {
                    "trial_id": trial.trial_id,
                    "calls": calls,
                }
            )

    # Phase results
    phase_results = store.get_phase_results(run_id)

    # Factor definitions
    factor_definitions = store.get_factor_definitions(run_id)

    # Report artifacts
    artifact_list = store.list_report_artifacts(run_id)
    report_artifacts: list[dict] = []
    for artifact_meta in artifact_list:
        artifact = store.get_report_artifact(run_id, artifact_meta["artifact_type"])
        if artifact is not None:
            report_artifacts.append(
                {
                    "artifact_type": artifact_meta["artifact_type"],
                    "data": artifact["data"],
                    "created_at": artifact["created_at"],
                }
            )

    bundle = {
        "format_version": FORMAT_VERSION,
        "run": {
            "run_id": summary.run_id,
            "run_type": summary.run_type,
            "status": summary.status,
            "created_at": summary.created_at,
            "finished_at": summary.finished_at,
            "config": summary.config,
            "pipeline_id": summary.pipeline_id,
            "phase": summary.phase,
        },
        "trials": trials_data,
        "traces": traces,
        "call_details": call_details,
        "phase_results": phase_results,
        "factor_definitions": factor_definitions,
        "report_artifacts": report_artifacts,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    logger.info("Exported run '%s' to %s", run_id, path)


def import_run(
    store: ObservatoryStore,
    path: Path,
    *,
    force: bool = False,
) -> str:
    """Import a run from a JSON bundle.

    Args:
        store: Destination observatory store.
        path: Path to the exported JSON bundle.
        force: If True, delete existing run with same ID before importing.

    Returns:
        The imported run_id.

    Raises:
        ValueError: If the run_id already exists and *force* is False.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    run_data = data["run"]
    run_id = run_data["run_id"]

    # Check for existing run
    try:
        store.get_run_summary(run_id)
        exists = True
    except ValueError:
        exists = False

    if exists:
        if not force:
            raise ValueError(
                f"Run '{run_id}' already exists. Use force=True to replace."
            )
        _delete_run(store, run_id)

    # Create run
    store.create_run(
        run_id=run_id,
        run_type=run_data["run_type"],
        config=run_data.get("config", {}),
        phase=run_data.get("phase"),
        pipeline_id=run_data.get("pipeline_id"),
    )

    # Build mapping from original trial_id -> new trial_id
    # (auto-increment IDs may differ between databases)
    trial_id_map: dict[int, int] = {}

    for trial_data in data.get("trials", []):
        original_trial_id = trial_data["trial_id"]
        new_trial_id = store.record_trial(
            run_id=run_id,
            task_id=trial_data["task_id"],
            task_type=trial_data["task_type"],
            variant_name=trial_data["variant_name"],
            repetition=trial_data["repetition"],
            score=trial_data["score"],
            prompt_tokens=trial_data["prompt_tokens"],
            completion_tokens=trial_data["completion_tokens"],
            total_tokens=trial_data["total_tokens"],
            cost=trial_data.get("cost"),
            latency_seconds=trial_data["latency_seconds"],
            model=trial_data["model"],
            source=trial_data.get("source", "gold_standard"),
            error=trial_data.get("error"),
            oa_row_id=trial_data.get("oa_row_id"),
            phase=trial_data.get("phase"),
            context_strategy=trial_data.get("context_strategy", "full_context"),
            llm_calls=trial_data.get("llm_calls", 1),
            strategy_metadata=trial_data.get("strategy_metadata"),
        )
        trial_id_map[original_trial_id] = new_trial_id

    # Record traces (map old trial_id -> new trial_id)
    for trace_data in data.get("traces", []):
        original_id = trace_data["trial_id"]
        new_id = trial_id_map.get(original_id)
        if new_id is not None:
            store.record_trace(
                trial_id=new_id,
                prompt_json=trace_data["prompt_json"],
                response_text=trace_data["response_text"],
            )

    # Save LLM call details (map old trial_id -> new trial_id)
    for detail in data.get("call_details", []):
        original_id = detail["trial_id"]
        new_id = trial_id_map.get(original_id)
        if new_id is not None:
            store.save_llm_call_details(new_id, detail["calls"])

    # Save factor definitions
    factor_defs = data.get("factor_definitions", [])
    if factor_defs:
        store.save_factor_definitions(run_id, factor_defs)

    # Save phase results
    phase_results = data.get("phase_results")
    if phase_results:
        store.save_phase_results(
            run_id=run_id,
            main_effects=phase_results.get("main_effects", {}),
            anova=phase_results.get("anova", {}),
            optimal=phase_results.get("optimal", {}),
            significant_factors=phase_results.get("significant_factors", []),
            quality_type=phase_results.get("quality_type", "larger_is_better"),
            total_cost=phase_results.get("total_cost", 0.0),
            total_tokens=phase_results.get("total_tokens", 0),
            elapsed_seconds=phase_results.get("elapsed_seconds", 0.0),
            interaction_effects=phase_results.get("interaction_effects", []),
        )

    # Save report artifacts
    for artifact in data.get("report_artifacts", []):
        store.save_report_artifact(
            run_id=run_id,
            artifact_type=artifact["artifact_type"],
            data=artifact["data"],
        )

    logger.info("Imported run '%s' from %s", run_id, path)
    return run_id


def _delete_run(store: ObservatoryStore, run_id: str) -> None:
    """Delete a run and all associated data in FK order.

    This is an internal helper used by force-import. It accesses
    store internals (_lock, _connect) directly.

    Args:
        store: The observatory store.
        run_id: The run to delete.
    """
    with store._lock, store._connect() as conn:
        # Delete in FK order: children first, then parent

        # llm_call_details -> via trial subquery
        conn.execute(
            "DELETE FROM llm_call_details WHERE trial_id IN "
            "(SELECT trial_id FROM trials WHERE run_id = ?)",
            (run_id,),
        )

        # trial_traces -> via trial subquery
        conn.execute(
            "DELETE FROM trial_traces WHERE trial_id IN "
            "(SELECT trial_id FROM trials WHERE run_id = ?)",
            (run_id,),
        )

        # trials
        conn.execute("DELETE FROM trials WHERE run_id = ?", (run_id,))

        # phase_results
        conn.execute("DELETE FROM phase_results WHERE run_id = ?", (run_id,))

        # factor_definitions
        conn.execute(
            "DELETE FROM factor_definitions WHERE run_id = ?", (run_id,)
        )

        # report_artifacts
        conn.execute(
            "DELETE FROM report_artifacts WHERE run_id = ?", (run_id,)
        )

        # runs
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    logger.info("Deleted run '%s' and all associated data", run_id)
