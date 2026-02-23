"""Tests for CompositeVariant – combines one variant per axis into a single render."""

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


@pytest.fixture()
def doc_tree() -> MagicMock:
    return _make_doc_tree()


@pytest.fixture()
def stub_a() -> StubVariant:
    return StubVariant(name="flat", axis=1, output="STRUCTURE_OUTPUT")


@pytest.fixture()
def stub_b() -> StubVariant:
    return StubVariant(name="summary", axis=2, output="METADATA_OUTPUT")


@pytest.fixture()
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

    def test_token_estimate_is_sum_of_components(
        self, stub_a: StubVariant, stub_b: StubVariant, stub_c: StubVariant
    ) -> None:
        composite = CompositeVariant(
            components={1: stub_a, 2: stub_b, 7: stub_c}
        )
        meta = composite.metadata()
        assert meta.token_estimate == 300  # 3 × 100

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
    """Verify render delegates and combines output."""

    def test_output_contains_all_components(
        self, stub_a: StubVariant, stub_b: StubVariant, doc_tree: MagicMock
    ) -> None:
        composite = CompositeVariant(components={1: stub_a, 2: stub_b})
        output = composite.render(doc_tree)
        assert "STRUCTURE_OUTPUT" in output
        assert "METADATA_OUTPUT" in output

    def test_output_is_nonempty(
        self, stub_a: StubVariant, doc_tree: MagicMock
    ) -> None:
        composite = CompositeVariant(components={1: stub_a})
        output = composite.render(doc_tree)
        assert len(output) > 0

    def test_render_applies_in_axis_order(
        self, doc_tree: MagicMock
    ) -> None:
        """Components should render in ascending axis order."""
        v7 = StubVariant(name="yaml", axis=7, output="SEVEN")
        v2 = StubVariant(name="summary", axis=2, output="TWO")
        v5 = StubVariant(name="medium", axis=5, output="FIVE")
        # Insert out of order to verify sorting
        composite = CompositeVariant(components={7: v7, 2: v2, 5: v5})
        output = composite.render(doc_tree)
        pos_two = output.index("TWO")
        pos_five = output.index("FIVE")
        pos_seven = output.index("SEVEN")
        assert pos_two < pos_five < pos_seven


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
