"""Tests for agent-index Pydantic data models."""

from datetime import UTC, datetime

import pytest
from agent_index.models import (
    DocFile,
    DocTree,
    IndexConfig,
    TierConfig,
    TransformStep,
)


class TestDocFile:
    """Tests for DocFile model."""

    def test_required_fields(self) -> None:
        """DocFile requires rel_path, content, size_bytes, tier, and section."""
        doc = DocFile(
            rel_path="guides/auth.md",
            content="# Authentication Guide",
            size_bytes=100,
            tier="required",
            section="Guides",
        )
        assert doc.rel_path == "guides/auth.md"
        assert doc.content == "# Authentication Guide"
        assert doc.size_bytes == 100
        assert doc.tier == "required"
        assert doc.section == "Guides"

    def test_default_values(self) -> None:
        """DocFile has sensible defaults for optional fields."""
        doc = DocFile(
            rel_path="api/users.md",
            content="# Users API",
            size_bytes=50,
            tier="reference",
            section="API",
        )
        assert doc.token_count is None
        assert doc.priority == 0
        assert doc.content_hash == ""
        assert doc.last_modified is None
        assert doc.summary is None
        assert doc.related == []

    def test_all_fields(self) -> None:
        """DocFile accepts all fields."""
        now = datetime.now(UTC)
        doc = DocFile(
            rel_path="guides/auth.md",
            content="# Auth",
            size_bytes=100,
            token_count=25,
            tier="required",
            section="Guides",
            priority=10,
            content_hash="abc123",
            last_modified=now,
            summary="Authentication guide",
            related=["guides/users.md", "api/auth.md"],
        )
        assert doc.token_count == 25
        assert doc.priority == 10
        assert doc.content_hash == "abc123"
        assert doc.last_modified == now
        assert doc.summary == "Authentication guide"
        assert doc.related == ["guides/users.md", "api/auth.md"]

    def test_serialization_roundtrip(self) -> None:
        """DocFile can be serialized to JSON and deserialized back."""
        now = datetime.now(UTC)
        original = DocFile(
            rel_path="test.md",
            content="test content",
            size_bytes=12,
            token_count=3,
            tier="recommended",
            section="Test",
            priority=5,
            content_hash="hash123",
            last_modified=now,
            summary="A test file",
            related=["other.md"],
        )
        json_str = original.model_dump_json()
        restored = DocFile.model_validate_json(json_str)
        assert restored == original

    def test_missing_required_field_raises(self) -> None:
        """DocFile raises ValidationError when required fields are missing."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DocFile(
                rel_path="test.md",
                content="content",
                # missing size_bytes, tier, section
            )


class TestDocTree:
    """Tests for DocTree model."""

    def test_required_fields(self) -> None:
        """DocTree requires files, scanned_at, and source."""
        now = datetime.now(UTC)
        tree = DocTree(
            files={},
            scanned_at=now,
            source="/path/to/docs",
        )
        assert tree.files == {}
        assert tree.scanned_at == now
        assert tree.source == "/path/to/docs"

    def test_default_total_tokens(self) -> None:
        """DocTree defaults total_tokens to 0."""
        now = datetime.now(UTC)
        tree = DocTree(
            files={},
            scanned_at=now,
            source=".",
        )
        assert tree.total_tokens == 0

    def test_with_files(self) -> None:
        """DocTree can contain DocFile instances."""
        now = datetime.now(UTC)
        doc = DocFile(
            rel_path="readme.md",
            content="# Readme",
            size_bytes=10,
            tier="required",
            section="Root",
        )
        tree = DocTree(
            files={"readme.md": doc},
            scanned_at=now,
            source="https://github.com/org/repo",
            total_tokens=100,
        )
        assert "readme.md" in tree.files
        assert tree.files["readme.md"].content == "# Readme"
        assert tree.total_tokens == 100

    def test_serialization_roundtrip(self) -> None:
        """DocTree can be serialized to JSON and deserialized back."""
        now = datetime.now(UTC)
        doc = DocFile(
            rel_path="test.md",
            content="test",
            size_bytes=4,
            tier="reference",
            section="Test",
        )
        original = DocTree(
            files={"test.md": doc},
            scanned_at=now,
            source="/docs",
            total_tokens=50,
        )
        json_str = original.model_dump_json()
        restored = DocTree.model_validate_json(json_str)
        assert restored == original


class TestTierConfig:
    """Tests for TierConfig model."""

    def test_required_fields(self) -> None:
        """TierConfig requires name and instruction."""
        tier = TierConfig(
            name="required",
            instruction="Read these files at session start.",
        )
        assert tier.name == "required"
        assert tier.instruction == "Read these files at session start."

    def test_default_patterns(self) -> None:
        """TierConfig defaults patterns to empty list."""
        tier = TierConfig(name="custom", instruction="Custom tier")
        assert tier.patterns == []

    def test_with_patterns(self) -> None:
        """TierConfig can have glob patterns for file assignment."""
        tier = TierConfig(
            name="api",
            instruction="API reference docs",
            patterns=["api/**/*.md", "reference/*.md"],
        )
        assert tier.patterns == ["api/**/*.md", "reference/*.md"]

    def test_serialization_roundtrip(self) -> None:
        """TierConfig can be serialized to JSON and deserialized back."""
        original = TierConfig(
            name="recommended",
            instruction="Read when relevant",
            patterns=["guides/*.md"],
        )
        json_str = original.model_dump_json()
        restored = TierConfig.model_validate_json(json_str)
        assert restored == original


class TestTransformStep:
    """Tests for TransformStep model."""

    def test_required_fields(self) -> None:
        """TransformStep requires type."""
        step = TransformStep(type="passthrough")
        assert step.type == "passthrough"

    def test_default_values(self) -> None:
        """TransformStep has sensible defaults."""
        step = TransformStep(type="algorithmic")
        assert step.strategy == "default"
        assert step.model is None

    def test_llm_step(self) -> None:
        """TransformStep can specify model for LLM steps."""
        step = TransformStep(
            type="llm",
            strategy="compressed",
            model="gpt-4o",
        )
        assert step.type == "llm"
        assert step.strategy == "compressed"
        assert step.model == "gpt-4o"

    def test_serialization_roundtrip(self) -> None:
        """TransformStep can be serialized to JSON and deserialized back."""
        original = TransformStep(
            type="llm",
            strategy="restructured",
            model="claude-3-opus",
        )
        json_str = original.model_dump_json()
        restored = TransformStep.model_validate_json(json_str)
        assert restored == original


class TestIndexConfig:
    """Tests for IndexConfig model."""

    def test_default_values(self) -> None:
        """IndexConfig has defaults matching DESIGN.md."""
        config = IndexConfig()

        # Basic settings
        assert config.index_name == "Docs Index"
        assert config.marker_id == "DOCS"
        assert config.root_path == "./.docs"
        assert (
            config.instruction == "Prefer retrieval-led reasoning over pre-training-led reasoning."
        )
        assert config.fallback_command == ""

        # Tiers
        assert len(config.tiers) == 3
        assert config.tiers[0].name == "required"
        assert config.tiers[0].instruction == "Read these files at the start of every session."
        assert config.tiers[1].name == "recommended"
        assert config.tiers[1].instruction == "Read these files when working on related tasks."
        assert config.tiers[2].name == "reference"
        assert config.tiers[2].instruction == "Consult these files when you need specific details."

        # Sources and file handling
        assert config.sources == []
        assert config.file_extensions == {".md", ".mdx", ".rst", ".txt"}
        assert config.ignore_patterns == ["node_modules", "__pycache__", ".git", ".venv"]

        # Output
        assert config.output_file == ""
        assert config.inject_into == ""
        assert config.format == "tiered"
        assert config.file_strategy == "colocate"

        # Transform
        assert len(config.transform_steps) == 1
        assert config.transform_steps[0].type == "passthrough"

        # LLM config
        assert config.llm_provider == ""
        assert config.llm_model == ""
        assert config.llm_base_url == ""

        # Output targets
        assert config.output_targets == ["agents.md"]

        # Performance
        assert config.max_workers == 8

    def test_custom_config(self) -> None:
        """IndexConfig accepts custom values."""
        config = IndexConfig(
            index_name="My Docs",
            marker_id="MYDOCS",
            root_path="/custom/docs",
            instruction="Custom instruction",
            fallback_command="agent-index scan",
            tiers=[
                TierConfig(name="critical", instruction="Must read"),
            ],
            sources=[{"type": "local", "path": "/docs"}],
            file_extensions={".md", ".txt"},
            ignore_patterns=["dist"],
            output_file="index.md",
            inject_into="README.md",
            format="flat",
            file_strategy="directory",
            transform_steps=[
                TransformStep(type="llm", strategy="compressed", model="gpt-4o"),
            ],
            llm_provider="openai",
            llm_model="gpt-4o",
            llm_base_url="https://api.openai.com/v1",
            output_targets=["claude.md", "cursor-rules"],
            max_workers=4,
        )

        assert config.index_name == "My Docs"
        assert config.marker_id == "MYDOCS"
        assert config.root_path == "/custom/docs"
        assert len(config.tiers) == 1
        assert config.tiers[0].name == "critical"
        assert config.sources == [{"type": "local", "path": "/docs"}]
        assert config.file_extensions == {".md", ".txt"}
        assert config.ignore_patterns == ["dist"]
        assert config.format == "flat"
        assert config.file_strategy == "directory"
        assert config.llm_provider == "openai"
        assert config.output_targets == ["claude.md", "cursor-rules"]
        assert config.max_workers == 4

    def test_serialization_roundtrip(self) -> None:
        """IndexConfig can be serialized to JSON and deserialized back."""
        original = IndexConfig(
            index_name="Test Index",
            marker_id="TEST",
            tiers=[
                TierConfig(name="main", instruction="Main docs"),
            ],
            transform_steps=[
                TransformStep(type="passthrough"),
                TransformStep(type="llm", model="gpt-4o"),
            ],
        )
        json_str = original.model_dump_json()
        restored = IndexConfig.model_validate_json(json_str)
        assert restored == original

    def test_file_extensions_set_handling(self) -> None:
        """IndexConfig handles set serialization correctly."""
        config = IndexConfig(file_extensions={".md", ".txt", ".rst"})
        json_str = config.model_dump_json()
        restored = IndexConfig.model_validate_json(json_str)
        # Sets may be serialized as lists; ensure they're equal as sets
        assert restored.file_extensions == config.file_extensions

    def test_default_tiers_are_independent(self) -> None:
        """Each IndexConfig instance gets its own tier list."""
        config1 = IndexConfig()
        config2 = IndexConfig()
        config1.tiers.append(TierConfig(name="extra", instruction="Extra tier"))
        # config2 should not be affected
        assert len(config2.tiers) == 3

    def test_default_transform_steps_are_independent(self) -> None:
        """Each IndexConfig instance gets its own transform_steps list."""
        config1 = IndexConfig()
        config2 = IndexConfig()
        config1.transform_steps.append(TransformStep(type="llm"))
        # config2 should not be affected
        assert len(config2.transform_steps) == 1
