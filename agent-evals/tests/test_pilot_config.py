"""Tests for pilot study configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PILOT_DIR = Path(__file__).resolve().parent.parent / "src" / "agent_evals" / "pilot"
CONFIG_PATH = PILOT_DIR / "config.yaml"


class TestPilotConfig:
    """Tests for pilot/config.yaml."""

    @pytest.fixture
    def config(self) -> dict:
        assert CONFIG_PATH.exists(), f"Config not found: {CONFIG_PATH}"
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_config_loads(self, config: dict) -> None:
        assert "pilot" in config

    def test_task_counts(self, config: dict) -> None:
        tasks = config["pilot"]["tasks"]
        assert tasks["per_type"] == 10
        assert tasks["total"] == 110

    def test_repetitions(self, config: dict) -> None:
        assert config["pilot"]["execution"]["repetitions"] == 3

    def test_axis_orderings_defined(self, config: dict) -> None:
        orderings = config["pilot"]["axis_orderings"]
        assert "default" in orderings
        assert len(orderings) >= 2
        for name, ordering in orderings.items():
            assert "order" in ordering, f"Missing 'order' in {name}"
            assert "description" in ordering, f"Missing 'description' in {name}"
            axes = ordering["order"]
            assert sorted(axes) == list(range(1, 11)), f"Ordering {name} must contain axes 1-10"

    def test_framing_strategies(self, config: dict) -> None:
        framing = config["pilot"]["framing"]
        assert "constant" in framing
        assert "adapted" in framing
        assert "system_prompt" in framing["constant"]
        assert "template" in framing["adapted"]

    def test_saturation_params(self, config: dict) -> None:
        sat = config["pilot"]["saturation"]
        assert sat["min_tasks"] > 0
        assert sat["step_size"] > 0
        assert 0 < sat["stability_threshold"] <= 5.0
        assert 0 < sat["tail_fraction"] <= 0.5
        assert 0 < sat["confidence_level"] < 1.0

    def test_thresholds(self, config: dict) -> None:
        thresholds = config["pilot"]["thresholds"]
        assert "ordering_sensitivity" in thresholds
        assert "framing_difference" in thresholds
        assert "saturation" in thresholds

    def test_model_config(self, config: dict) -> None:
        model = config["pilot"]["model"]
        assert "default" in model
        assert "judge" in model

    def test_sampling_seed_set(self, config: dict) -> None:
        assert config["pilot"]["tasks"]["seed"] == 42
