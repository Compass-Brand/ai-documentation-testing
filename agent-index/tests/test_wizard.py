"""Tests for interactive wizard data flow."""

from __future__ import annotations

from agent_index.models import IndexConfig
from agent_index.wizard import WizardAnswers, build_config_from_answers


class TestWizardAnswers:
    """Tests for the WizardAnswers dataclass."""

    def test_fields_populated(self) -> None:
        """WizardAnswers stores all fields correctly."""
        answers = WizardAnswers(
            project_name="Test Project",
            doc_locations=["./docs", "./guides"],
            tiers=["required", "recommended"],
            output_targets=["agents.md", "claude.md"],
            instruction="Custom instruction.",
        )

        assert answers.project_name == "Test Project"
        assert answers.doc_locations == ["./docs", "./guides"]
        assert answers.tiers == ["required", "recommended"]
        assert answers.output_targets == ["agents.md", "claude.md"]
        assert answers.instruction == "Custom instruction."

    def test_default_values(self) -> None:
        """WizardAnswers has sensible defaults."""
        answers = WizardAnswers(project_name="Minimal")

        assert answers.project_name == "Minimal"
        assert answers.doc_locations == []
        assert answers.tiers == ["required", "recommended", "reference"]
        assert answers.output_targets == ["agents.md"]
        assert "retrieval-led" in answers.instruction


class TestBuildConfigFromAnswers:
    """Tests for the build_config_from_answers function."""

    def test_produces_valid_index_config(self) -> None:
        """build_config_from_answers returns a valid IndexConfig."""
        answers = WizardAnswers(
            project_name="My Project",
            doc_locations=["./docs"],
            tiers=["required", "recommended", "reference"],
        )

        config = build_config_from_answers(answers)

        assert isinstance(config, IndexConfig)
        assert config.index_name == "My Project"

    def test_maps_tier_names_correctly(self) -> None:
        """Tier names are mapped to TierConfig objects with correct names."""
        answers = WizardAnswers(
            project_name="Test",
            tiers=["required", "reference"],
        )

        config = build_config_from_answers(answers)

        assert len(config.tiers) == 2
        assert config.tiers[0].name == "required"
        assert config.tiers[1].name == "reference"

    def test_tier_instructions_set(self) -> None:
        """Known tiers get default instructions."""
        answers = WizardAnswers(
            project_name="Test",
            tiers=["required", "recommended", "reference"],
        )

        config = build_config_from_answers(answers)

        required = next(t for t in config.tiers if t.name == "required")
        assert "start of every session" in required.instruction

        reference = next(t for t in config.tiers if t.name == "reference")
        assert "specific details" in reference.instruction

    def test_sets_output_targets(self) -> None:
        """Output targets from answers are set on the config."""
        answers = WizardAnswers(
            project_name="Test",
            output_targets=["agents.md", "claude.md", "cursor-rules"],
        )

        config = build_config_from_answers(answers)

        assert config.output_targets == ["agents.md", "claude.md", "cursor-rules"]

    def test_minimal_input(self) -> None:
        """build_config_from_answers works with just a project name."""
        answers = WizardAnswers(project_name="Bare Minimum")

        config = build_config_from_answers(answers)

        assert isinstance(config, IndexConfig)
        assert config.index_name == "Bare Minimum"
        # Default root_path when no doc_locations
        assert config.root_path == "./.docs"
        # Default tiers
        assert len(config.tiers) == 3

    def test_custom_instruction(self) -> None:
        """Custom instruction is passed through to IndexConfig."""
        answers = WizardAnswers(
            project_name="Test",
            instruction="Always check the API docs first.",
        )

        config = build_config_from_answers(answers)

        assert config.instruction == "Always check the API docs first."

    def test_custom_tier_name(self) -> None:
        """Custom (non-standard) tier names get a default instruction."""
        answers = WizardAnswers(
            project_name="Test",
            tiers=["critical", "optional"],
        )

        config = build_config_from_answers(answers)

        assert len(config.tiers) == 2
        assert config.tiers[0].name == "critical"
        assert "critical" in config.tiers[0].instruction
        assert config.tiers[1].name == "optional"
        assert "optional" in config.tiers[1].instruction

    def test_root_path_from_doc_locations(self) -> None:
        """Root path set from first doc_location."""
        answers = WizardAnswers(
            project_name="Test",
            doc_locations=["./my-docs", "./other"],
        )

        config = build_config_from_answers(answers)

        assert config.root_path == "./my-docs"
