"""Tests for CompositeVariant - combines one variant per axis into a single render."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.composite import CompositeVariant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubVariant(IndexVariant):
    """Minimal test stub that records lifecycle calls."""

    def __init__(self, name: str, axis: int, output: str) -> None:
        self._name = name
        self._axis = axis
        self._output = output
        self.setup_calls: list[object] = []
        self.teardown_calls: int = 0

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name=self._name,
            axis=self._axis,
            category="stub",
            description=f"Stub variant for axis {self._axis}",
            token_estimate=100,
        )

    def render(self, doc_tree: object) -> str:
        return self._output

    def setup(self, doc_tree: object) -> None:
        self.setup_calls.append(doc_tree)

    def teardown(self) -> None:
        self.teardown_calls += 1


def _make_doc_tree() -> MagicMock:
    """Create a minimal mock DocTree for testing."""
    tree = MagicMock()
    tree.files = {}
    return tree


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def doc_tree() -> MagicMock:
    return _make_doc_tree()


@pytest.fixture
def stub_a() -> StubVariant:
    return StubVariant(name="flat", axis=1, output="STRUCTURE_OUTPUT")


@pytest.fixture
def stub_b() -> StubVariant:
    return StubVariant(name="summary", axis=2, output="METADATA_OUTPUT")


@pytest.fixture
def stub_c() -> StubVariant:
    return StubVariant(name="yaml", axis=7, output="FORMAT_OUTPUT")


# ---------------------------------------------------------------------------
# TestCompositeVariantCreation
# ---------------------------------------------------------------------------


class TestCompositeVariantCreation:
    """Verify construction and input validation."""

    def test_accepts_valid_components(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        assert composite is not None

    def test_rejects_empty_components(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            CompositeVariant(components={})

    def test_accepts_single_component(self, stub_a: StubVariant) -> None:
        composite = CompositeVariant(components={1: stub_a})
        assert composite is not None


# ---------------------------------------------------------------------------
# TestCompositeVariantMetadata
# ---------------------------------------------------------------------------


class TestCompositeVariantMetadata:
    """Verify composite metadata combines component information."""

    def test_name_contains_all_component_names(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        meta = composite.metadata()
        assert "flat" in meta.name
        assert "summary" in meta.name

    def test_axis_is_zero_for_composite(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        meta = composite.metadata()
        assert meta.axis == 0

    def test_category_is_composite(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        meta = composite.metadata()
        assert meta.category == "composite"

    def test_token_estimate_is_primary_only(
        self, stub_a: StubVariant, stub_b: StubVariant, stub_c: StubVariant
    ) -> None:
        """Bug #182: token_estimate should reflect only the primary renderer, not sum of all."""
        composite = CompositeVariant(
            components={1: stub_a, 2: stub_b, 7: stub_c}
        )
        meta = composite.metadata()
        # Only the primary (lowest axis = 1, token_estimate=100) should count
        assert meta.token_estimate == 100

    def test_description_mentions_composite(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        meta = composite.metadata()
        assert "composite" in meta.description.lower()


# ---------------------------------------------------------------------------
# TestCompositeVariantRender
# ---------------------------------------------------------------------------


class TestCompositeVariantRender:
    """Verify render uses pipeline: one primary renders, not all."""

    def test_primary_component_output_present(
        self, stub_a: StubVariant, stub_b: StubVariant, doc_tree: MagicMock
    ) -> None:
        """With multiple PRIMARY components, the lowest-axis one renders."""
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        output = composite.render(doc_tree)
        # Lowest axis (1) is the primary renderer
        assert "STRUCTURE_OUTPUT" in output

    def test_output_is_nonempty(
        self, stub_a: StubVariant, doc_tree: MagicMock
    ) -> None:
        composite = CompositeVariant(components={1: stub_a})
        output = composite.render(doc_tree)
        assert len(output) > 0

    def test_single_primary_renders_not_all(
        self, doc_tree: MagicMock
    ) -> None:
        """Only one primary component renders to avoid prompt inflation."""
        v7 = StubVariant(name="yaml", axis=7, output="SEVEN")
        v2 = StubVariant(name="summary", axis=2, output="TWO")
        v5 = StubVariant(name="medium", axis=5, output="FIVE")
        composite = CompositeVariant(components={7: v7, 2: v2, 5: v5})
        output = composite.render(doc_tree)
        # Only the lowest axis (2) renders as primary
        assert "TWO" in output
        # Others do NOT concatenate their full render
        assert output.count("TWO") == 1

    def test_deduplicates_identical_h1_headers(
        self, doc_tree: MagicMock
    ) -> None:
        """Duplicate H1 headers across components should be collapsed."""
        v1 = StubVariant(
            name="pos", axis=1,
            output="# Documentation Index\n\n- file_a.md",
        )
        v3 = StubVariant(
            name="fmt", axis=3,
            output="# Documentation Index\n\n| Path |\n|------|\n| file_a.md |",
        )
        composite = CompositeVariant(components={1: v1, 3: v3})
        output = composite.render(doc_tree)
        assert output.count("# Documentation Index") == 1

    def test_pipeline_renders_only_primary(
        self, doc_tree: MagicMock
    ) -> None:
        """Only the lowest-axis PRIMARY component should render."""
        v1 = StubVariant(
            name="pos", axis=1,
            output="# Documentation Index\n\ncontent a",
        )
        v3 = StubVariant(
            name="fmt", axis=3,
            output="# API Reference\n\ncontent b",
        )
        composite = CompositeVariant(components={1: v1, 3: v3})
        output = composite.render(doc_tree)
        # Axis 1 is the primary renderer (lowest axis)
        assert "# Documentation Index" in output
        assert "content a" in output
        # Axis 3 does NOT render its full output
        assert "# API Reference" not in output

    def test_pipeline_picks_lowest_axis_as_primary(
        self, doc_tree: MagicMock
    ) -> None:
        """When all components are PRIMARY, the lowest axis renders."""
        v1 = StubVariant(name="a", axis=1, output="# Documentation Index\n\nA")
        v2 = StubVariant(name="b", axis=2, output="# Documentation Index\n\nB")
        v3 = StubVariant(name="c", axis=3, output="# Documentation Index\n\nC")
        composite = CompositeVariant(
            components={1: v1, 2: v2, 3: v3}
        )
        output = composite.render(doc_tree)
        assert output.count("# Documentation Index") == 1
        assert "A" in output
        # Only axis 1 renders
        assert output == "# Documentation Index\n\nA"

    def test_pipeline_single_render_no_concatenation(
        self, doc_tree: MagicMock
    ) -> None:
        """Pipeline produces exactly the primary's output, not concatenated."""
        v1 = StubVariant(name="a", axis=1, output="files:\n  - path: a.md")
        v2 = StubVariant(name="b", axis=2, output="no header here")
        composite = CompositeVariant(components={1: v1, 2: v2})
        output = composite.render(doc_tree)
        # Only axis 1 renders as primary
        assert "files:\n  - path: a.md" in output
        assert "no header here" not in output


# ---------------------------------------------------------------------------
# TestCompositeVariantLifecycle
# ---------------------------------------------------------------------------


class TestCompositeVariantLifecycle:
    """Verify setup/teardown delegation to all components."""

    def test_setup_calls_all_components(
        self,
        stub_a: StubVariant,
        stub_b: StubVariant,
        doc_tree: MagicMock,
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        composite.setup(doc_tree)
        assert len(stub_a.setup_calls) == 1
        assert stub_a.setup_calls[0] is doc_tree
        assert len(stub_b.setup_calls) == 1
        assert stub_b.setup_calls[0] is doc_tree

    def test_teardown_calls_all_components(
        self, stub_a: StubVariant, stub_b: StubVariant
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        composite.teardown()
        assert stub_a.teardown_calls == 1
        assert stub_b.teardown_calls == 1

    def test_setup_delegates_in_axis_order(
        self, doc_tree: MagicMock
    ) -> None:
        """Setup should call components in ascending axis order."""
        call_order: list[int] = []

        class OrderTracker(StubVariant):
            def setup(self, doc_tree: object) -> None:
                call_order.append(self._axis)

        v3 = OrderTracker(name="a", axis=3, output="")
        v1 = OrderTracker(name="b", axis=1, output="")
        composite = CompositeVariant(components={3: v3, 1: v1})
        composite.setup(doc_tree)
        assert call_order == [1, 3]
