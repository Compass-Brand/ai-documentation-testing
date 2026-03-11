"""Tests for CompositeVariant pipeline rendering (Bug #135).

Verifies that CompositeVariant produces ONE coherent rendering instead of
concatenating N independent full renderings (which inflated prompts 10x).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agent_evals.variants.base import IndexVariant, PipelineRole, VariantMetadata
from agent_evals.variants.composite import CompositeVariant
from agent_index.models import DocFile, DocTree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc_file(
    rel_path: str,
    section: str = "API",
    tier: str = "required",
    content: str = "Default content for testing.",
    priority: int = 0,
    token_count: int = 100,
    summary: str | None = None,
    last_modified: datetime | None = None,
) -> DocFile:
    """Create a DocFile with sensible defaults."""
    return DocFile(
        rel_path=rel_path,
        content=content,
        size_bytes=len(content),
        token_count=token_count,
        tier=tier,
        section=section,
        priority=priority,
        summary=summary,
        last_modified=last_modified,
    )


def _make_doc_tree(num_files: int = 4) -> DocTree:
    """Create a DocTree with realistic files for composite testing."""
    file_specs = [
        ("api/auth.md", "API", "required", "JWT authentication with AuthMiddleware"),
        ("api/caching.md", "API", "recommended", "Response caching with CacheConfig"),
        ("guides/setup.md", "Guides", "required", "Getting started guide for devs"),
        ("guides/advanced.md", "Guides", "reference", "Advanced configuration tips"),
        ("api/errors.md", "API", "reference", "Error handling and status codes"),
        ("guides/deploy.md", "Guides", "recommended", "Deployment best practices"),
        ("internal/changelog.md", "Internal", "reference", "Release notes and changes"),
        ("internal/roadmap.md", "Internal", "reference", "Future development roadmap"),
    ][:num_files]

    files: dict[str, DocFile] = {}
    for rel_path, section, tier, content in file_specs:
        files[rel_path] = _make_doc_file(
            rel_path=rel_path,
            section=section,
            tier=tier,
            content=content,
        )

    return DocTree(
        files=files,
        scanned_at=datetime(2026, 1, 1, tzinfo=UTC),
        source="/test/docs",
        total_tokens=sum(f.token_count or 0 for f in files.values()),
    )


class StubPrimaryRenderer(IndexVariant):
    """Stub that acts as a primary renderer (e.g., format axis)."""

    def __init__(self, axis: int = 3) -> None:
        self._axis = axis

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="stub-primary",
            axis=self._axis,
            category="format",
            description="Stub primary renderer",
            token_estimate=200,
        )

    def pipeline_role(self) -> PipelineRole:
        return PipelineRole.PRIMARY

    def render(self, doc_tree: DocTree) -> str:
        lines = ["files:"]
        for key in sorted(doc_tree.files):
            doc = doc_tree.files[key]
            lines.append(f"  - path: {doc.rel_path}")
            lines.append(f"    tier: {doc.tier}")
        return "\n".join(lines)


class StubPreFilter(IndexVariant):
    """Stub that pre-filters the doc tree (e.g., scale axis)."""

    def __init__(self, max_files: int = 2, axis: int = 6) -> None:
        self._max_files = max_files
        self._axis = axis

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="stub-pre-filter",
            axis=self._axis,
            category="scale",
            description="Stub pre-filter",
            token_estimate=100,
        )

    def pipeline_role(self) -> PipelineRole:
        return PipelineRole.PRE_RENDER

    def pre_render(self, doc_tree: DocTree) -> DocTree:
        sorted_keys = sorted(doc_tree.files)[:self._max_files]
        filtered = {k: doc_tree.files[k] for k in sorted_keys}
        return doc_tree.model_copy(update={"files": filtered})

    def render(self, doc_tree: DocTree) -> str:
        # Fallback for standalone use
        lines = []
        for key in sorted(doc_tree.files)[:self._max_files]:
            doc = doc_tree.files[key]
            lines.append(f"- {doc.rel_path}: filtered")
        return "\n".join(lines)


class StubPostTransform(IndexVariant):
    """Stub that post-transforms the rendered text (e.g., temporal axis)."""

    def __init__(self, suffix: str = "[TAGGED]", axis: int = 10) -> None:
        self._suffix = suffix
        self._axis = axis

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="stub-post-transform",
            axis=self._axis,
            category="temporal",
            description="Stub post-transform",
            token_estimate=50,
        )

    def pipeline_role(self) -> PipelineRole:
        return PipelineRole.POST_RENDER

    def post_render(self, text: str, doc_tree: DocTree) -> str:
        return text + f"\n{self._suffix}"

    def render(self, doc_tree: DocTree) -> str:
        lines = []
        for key in sorted(doc_tree.files):
            doc = doc_tree.files[key]
            lines.append(f"- {doc.rel_path} {self._suffix}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def doc_tree() -> DocTree:
    """4-file doc tree for pipeline tests."""
    return _make_doc_tree(4)


@pytest.fixture
def large_doc_tree() -> DocTree:
    """8-file doc tree for size inflation tests."""
    return _make_doc_tree(8)


# ---------------------------------------------------------------------------
# TestPipelineRole
# ---------------------------------------------------------------------------


class TestPipelineRole:
    """Verify PipelineRole enum and default behaviour on IndexVariant."""

    def test_pipeline_role_has_three_values(self) -> None:
        assert PipelineRole.PRIMARY is not None
        assert PipelineRole.PRE_RENDER is not None
        assert PipelineRole.POST_RENDER is not None

    def test_default_pipeline_role_is_primary(self) -> None:
        """Existing variants that don't override pipeline_role default to PRIMARY."""
        stub = StubPrimaryRenderer()
        assert stub.pipeline_role() == PipelineRole.PRIMARY

    def test_pre_render_default_is_identity(self, doc_tree: DocTree) -> None:
        """Base class pre_render returns the doc_tree unchanged."""
        stub = StubPrimaryRenderer()
        result = stub.pre_render(doc_tree)
        assert result is doc_tree

    def test_post_render_default_is_identity(self, doc_tree: DocTree) -> None:
        """Base class post_render returns the text unchanged."""
        stub = StubPrimaryRenderer()
        result = stub.post_render("hello", doc_tree)
        assert result == "hello"


# ---------------------------------------------------------------------------
# TestCompositeNoInflation
# ---------------------------------------------------------------------------


class TestCompositeNoInflation:
    """The core bug: composite output must NOT be N*single_render size."""

    def test_composite_output_not_inflated(
        self, large_doc_tree: DocTree
    ) -> None:
        """With 3 components, output should be ~1x a single render, not 3x."""
        primary = StubPrimaryRenderer(axis=3)
        pre_filter = StubPreFilter(max_files=8, axis=6)
        post_transform = StubPostTransform(axis=10)

        # Single-axis render size
        single_output = primary.render(large_doc_tree)
        single_len = len(single_output)

        # Composite render size
        composite = CompositeVariant(
            components={3: primary, 6: pre_filter, 10: post_transform}
        )
        composite_output = composite.render(large_doc_tree)

        # Should be close to single_len + small overhead, NOT 3x
        assert len(composite_output) < single_len * 1.5

    def test_ten_axis_composite_not_ten_x(
        self, large_doc_tree: DocTree
    ) -> None:
        """With 10 components, output must stay under 2x a single render."""
        primary = StubPrimaryRenderer(axis=3)
        pre_filter = StubPreFilter(max_files=8, axis=6)

        # Create post-transform stubs for axes 1, 2, 4, 5, 7, 8, 9, 10
        others: dict[int, IndexVariant] = {}
        for ax in [1, 2, 4, 5, 7, 8, 9, 10]:
            others[ax] = StubPostTransform(suffix=f"[AXIS-{ax}]", axis=ax)

        components: dict[int, IndexVariant] = {3: primary, 6: pre_filter}
        components.update(others)

        single_output = primary.render(large_doc_tree)
        single_len = len(single_output)

        composite = CompositeVariant(components=components)
        composite_output = composite.render(large_doc_tree)

        # With 10 axes, old code would produce ~10x; new code < 2x
        assert len(composite_output) < single_len * 2.0


# ---------------------------------------------------------------------------
# TestCompositeCoherentOutput
# ---------------------------------------------------------------------------


class TestCompositeCoherentOutput:
    """Output must be a single coherent document, not concatenated parts."""

    def test_single_coherent_rendering(
        self, doc_tree: DocTree
    ) -> None:
        """Output should contain one rendering of the file list, not multiple."""
        primary = StubPrimaryRenderer(axis=3)
        post = StubPostTransform(axis=10)

        composite = CompositeVariant(
            components={3: primary, 10: post}
        )
        output = composite.render(doc_tree)

        # The primary renderer produces "files:" header once
        assert output.count("files:") == 1

    def test_file_paths_appear_once(self, doc_tree: DocTree) -> None:
        """Each file path should appear only once in the rendered output."""
        primary = StubPrimaryRenderer(axis=3)
        post = StubPostTransform(suffix="[DATED]", axis=10)

        composite = CompositeVariant(
            components={3: primary, 10: post}
        )
        output = composite.render(doc_tree)

        for key in doc_tree.files:
            count = output.count(key)
            assert count == 1, f"{key} appears {count} times, expected 1"


# ---------------------------------------------------------------------------
# TestPipelineOrdering
# ---------------------------------------------------------------------------


class TestPipelineOrdering:
    """Pre-render happens before primary, post-render after."""

    def test_pre_render_filters_before_primary(
        self, doc_tree: DocTree
    ) -> None:
        """Pre-render filter should reduce files before primary renders."""
        pre_filter = StubPreFilter(max_files=2, axis=6)
        primary = StubPrimaryRenderer(axis=3)

        composite = CompositeVariant(
            components={3: primary, 6: pre_filter}
        )
        output = composite.render(doc_tree)

        # Only 2 files should appear (first 2 sorted)
        sorted_keys = sorted(doc_tree.files)
        for key in sorted_keys[:2]:
            assert key in output
        for key in sorted_keys[2:]:
            assert key not in output

    def test_post_render_modifies_output(
        self, doc_tree: DocTree
    ) -> None:
        """Post-render should add its content to the primary output."""
        primary = StubPrimaryRenderer(axis=3)
        post = StubPostTransform(suffix="[TEMPORAL-MARKER]", axis=10)

        composite = CompositeVariant(
            components={3: primary, 10: post}
        )
        output = composite.render(doc_tree)

        assert "[TEMPORAL-MARKER]" in output

    def test_multiple_pre_renders_chain(
        self, large_doc_tree: DocTree
    ) -> None:
        """Multiple pre-render components chain: each narrows further."""
        # First filter to 5 files, second to 3
        pre1 = StubPreFilter(max_files=5, axis=6)
        pre2 = StubPreFilter(max_files=3, axis=7)
        primary = StubPrimaryRenderer(axis=3)

        composite = CompositeVariant(
            components={3: primary, 6: pre1, 7: pre2}
        )
        output = composite.render(large_doc_tree)

        # Count file entries — should be 3 (the tighter filter wins after chaining)
        sorted_keys = sorted(large_doc_tree.files)
        for key in sorted_keys[:3]:
            assert key in output
        for key in sorted_keys[3:]:
            assert key not in output

    def test_multiple_post_renders_chain(
        self, doc_tree: DocTree
    ) -> None:
        """Multiple post-render transforms chain in axis order."""
        primary = StubPrimaryRenderer(axis=3)
        post1 = StubPostTransform(suffix="[XREF]", axis=9)
        post2 = StubPostTransform(suffix="[TEMPORAL]", axis=10)

        composite = CompositeVariant(
            components={3: primary, 9: post1, 10: post2}
        )
        output = composite.render(doc_tree)

        assert "[XREF]" in output
        assert "[TEMPORAL]" in output
        # XREF should come before TEMPORAL (axis 9 < axis 10)
        assert output.index("[XREF]") < output.index("[TEMPORAL]")


# ---------------------------------------------------------------------------
# TestBackwardCompatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Existing single-axis and legacy composites must still work."""

    def test_single_component_composite_works(
        self, doc_tree: DocTree
    ) -> None:
        """A CompositeVariant with one component should render normally."""
        primary = StubPrimaryRenderer(axis=3)
        composite = CompositeVariant(components={3: primary})
        output = composite.render(doc_tree)

        # Should match the primary's direct render
        expected = primary.render(doc_tree)
        assert output == expected

    def test_all_primary_components_picks_one(
        self, doc_tree: DocTree
    ) -> None:
        """When all components are PRIMARY, exactly one should render."""

        class PrimaryStub(IndexVariant):
            def __init__(self, name: str, axis: int) -> None:
                self._name = name
                self._axis = axis

            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name=self._name,
                    axis=self._axis,
                    category="test",
                    description="test",
                    token_estimate=100,
                )

            def render(self, doc_tree: DocTree) -> str:
                lines = []
                for key in sorted(doc_tree.files):
                    lines.append(f"- {key}: {self._name}")
                return "\n".join(lines)

        v1 = PrimaryStub("axis-1", axis=1)
        v2 = PrimaryStub("axis-2", axis=2)
        v3 = PrimaryStub("axis-3", axis=3)

        composite = CompositeVariant(components={1: v1, 2: v2, 3: v3})
        output = composite.render(doc_tree)

        # Each file path should appear exactly once
        for key in doc_tree.files:
            assert output.count(key) == 1, (
                f"{key} appears {output.count(key)} times"
            )

    def test_legacy_stub_variant_defaults_to_primary(
        self, doc_tree: DocTree
    ) -> None:
        """Variants without pipeline_role() override default to PRIMARY."""

        class LegacyVariant(IndexVariant):
            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name="legacy",
                    axis=1,
                    category="test",
                    description="test",
                    token_estimate=100,
                )

            def render(self, doc_tree: DocTree) -> str:
                return "legacy-output"

        legacy = LegacyVariant()
        assert legacy.pipeline_role() == PipelineRole.PRIMARY

    def test_composite_metadata_unchanged(self) -> None:
        """Pipeline changes should not affect metadata generation."""
        primary = StubPrimaryRenderer(axis=3)
        pre = StubPreFilter(axis=6)
        post = StubPostTransform(axis=10)

        composite = CompositeVariant(
            components={3: primary, 6: pre, 10: post}
        )
        meta = composite.metadata()

        assert "stub-primary" in meta.name
        assert "stub-pre-filter" in meta.name
        assert "stub-post-transform" in meta.name
        assert meta.category == "composite"
        assert meta.token_estimate == 200  # primary only (bug #182)


# ---------------------------------------------------------------------------
# TestCompositeSetupTeardown
# ---------------------------------------------------------------------------


class TestCompositeSetupTeardown:
    """Setup/teardown delegation must still work with the pipeline."""

    def test_setup_calls_all_components(self, doc_tree: DocTree) -> None:
        """Setup should still delegate to all components."""
        setup_calls: list[int] = []

        class TrackedVariant(IndexVariant):
            def __init__(self, axis: int) -> None:
                self._axis = axis

            def metadata(self) -> VariantMetadata:
                return VariantMetadata(
                    name=f"tracked-{self._axis}",
                    axis=self._axis,
                    category="test",
                    description="test",
                    token_estimate=100,
                )

            def render(self, doc_tree: DocTree) -> str:
                return ""

            def setup(self, doc_tree: DocTree) -> None:
                setup_calls.append(self._axis)

        composite = CompositeVariant(
            components={3: TrackedVariant(3), 6: TrackedVariant(6)}
        )
        composite.setup(doc_tree)

        assert 3 in setup_calls
        assert 6 in setup_calls


# ---------------------------------------------------------------------------
# TestCompositeEdgeCases
# ---------------------------------------------------------------------------


class TestCompositeEdgeCases:
    """Edge cases and error handling for CompositeVariant."""

    def test_no_primary_component_uses_fallback(
        self, doc_tree: DocTree
    ) -> None:
        """Render falls back to passthrough when no PRIMARY components exist."""
        pre = StubPreFilter(max_files=2, axis=6)
        post = StubPostTransform(suffix="[TAG]", axis=10)

        composite = CompositeVariant(components={6: pre, 10: post})
        output = composite.render(doc_tree)
        assert isinstance(output, str)

    def test_empty_components_raises(self) -> None:
        """Empty components dict must raise ValueError."""
        with pytest.raises(ValueError, match="at least one component"):
            CompositeVariant(components={})
