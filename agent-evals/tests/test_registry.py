"""Tests for variant base class and registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    register_variant,
)

if TYPE_CHECKING:
    from agent_index.models import DocTree


# ---------------------------------------------------------------------------
# Helpers: concrete dummy variants for testing
# ---------------------------------------------------------------------------


class _DummyVariantAxis1(IndexVariant):
    """A concrete variant on axis 1 used for testing."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="dummy-axis1",
            axis=1,
            category="test",
            description="Dummy variant for axis 1",
            token_estimate=100,
        )

    def render(self, doc_tree: DocTree) -> str:
        return "axis-1-output"


class _DummyVariantAxis1B(IndexVariant):
    """A second variant on axis 1 for multi-variant tests."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="dummy-axis1b",
            axis=1,
            category="test",
            description="Second dummy variant for axis 1",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        return "axis-1b-output"


class _DummyVariantAxis3(IndexVariant):
    """A concrete variant on axis 3 used for testing."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="dummy-axis3",
            axis=3,
            category="test",
            description="Dummy variant for axis 3",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        return "axis-3-output"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


# ---------------------------------------------------------------------------
# VariantMetadata tests
# ---------------------------------------------------------------------------


class TestVariantMetadata:
    """Tests for the VariantMetadata Pydantic model."""

    def test_creates_valid_metadata(self) -> None:
        """VariantMetadata accepts valid field values."""
        meta = VariantMetadata(
            name="flat-list",
            axis=1,
            category="structure",
            description="A flat list of files",
            token_estimate=500,
        )
        assert meta.name == "flat-list"
        assert meta.axis == 1
        assert meta.category == "structure"
        assert meta.description == "A flat list of files"
        assert meta.token_estimate == 500

    def test_axis_must_be_at_least_0(self) -> None:
        """VariantMetadata rejects axis values below 0."""
        with pytest.raises(ValueError):
            VariantMetadata(
                name="bad",
                axis=-1,
                category="test",
                description="Invalid axis",
                token_estimate=100,
            )

    def test_axis_must_be_at_most_10(self) -> None:
        """VariantMetadata rejects axis values above 10."""
        with pytest.raises(ValueError):
            VariantMetadata(
                name="bad",
                axis=11,
                category="test",
                description="Invalid axis",
                token_estimate=100,
            )

    def test_token_estimate_allows_zero(self) -> None:
        """VariantMetadata accepts zero token estimate (populated after render)."""
        meta = VariantMetadata(
            name="pre-render",
            axis=1,
            category="test",
            description="Token estimate before render",
        )
        assert meta.token_estimate == 0

    def test_token_estimate_rejects_negative(self) -> None:
        """VariantMetadata rejects negative token estimates."""
        with pytest.raises(ValueError):
            VariantMetadata(
                name="bad",
                axis=1,
                category="test",
                description="Invalid tokens",
                token_estimate=-1,
            )


# ---------------------------------------------------------------------------
# IndexVariant ABC tests
# ---------------------------------------------------------------------------


class TestIndexVariant:
    """Tests for the IndexVariant abstract base class."""

    def test_concrete_variant_implements_metadata(self) -> None:
        """Concrete variant returns VariantMetadata from metadata()."""
        variant = _DummyVariantAxis1()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "dummy-axis1"

    def test_concrete_variant_implements_render(self) -> None:
        """Concrete variant returns a string from render()."""
        variant = _DummyVariantAxis1()
        # We pass None as doc_tree since the dummy doesn't use it
        result = variant.render(None)  # type: ignore[arg-type]
        assert result == "axis-1-output"

    def test_setup_is_optional_noop(self) -> None:
        """Default setup() does nothing and doesn't raise."""
        variant = _DummyVariantAxis1()
        variant.setup(None)  # type: ignore[arg-type]

    def test_teardown_is_optional_noop(self) -> None:
        """Default teardown() does nothing and doesn't raise."""
        variant = _DummyVariantAxis1()
        variant.teardown()

    def test_cannot_instantiate_abc_directly(self) -> None:
        """IndexVariant cannot be instantiated without implementing abstract methods."""
        with pytest.raises(TypeError):
            IndexVariant()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Registry: register_variant tests
# ---------------------------------------------------------------------------


class TestRegisterVariant:
    """Tests for the register_variant function."""

    def test_register_single_variant(self) -> None:
        """register_variant adds a variant class to the registry."""
        register_variant(_DummyVariantAxis1)
        all_variants = get_all_variants()
        assert len(all_variants) == 1
        assert all_variants[0].metadata().name == "dummy-axis1"

    def test_register_multiple_variants(self) -> None:
        """register_variant can register multiple variant classes."""
        register_variant(_DummyVariantAxis1)
        register_variant(_DummyVariantAxis3)
        all_variants = get_all_variants()
        assert len(all_variants) == 2
        names = {v.metadata().name for v in all_variants}
        assert names == {"dummy-axis1", "dummy-axis3"}

    def test_register_duplicate_is_idempotent(self) -> None:
        """Registering the same class twice does not create duplicates."""
        register_variant(_DummyVariantAxis1)
        register_variant(_DummyVariantAxis1)
        all_variants = get_all_variants()
        assert len(all_variants) == 1

    def test_register_returns_class_for_decorator_use(self) -> None:
        """register_variant returns the class so it can be used as a decorator."""
        result = register_variant(_DummyVariantAxis1)
        assert result is _DummyVariantAxis1


# ---------------------------------------------------------------------------
# Registry: get_variants_for_axis tests
# ---------------------------------------------------------------------------


class TestGetVariantsForAxis:
    """Tests for get_variants_for_axis."""

    def test_returns_empty_list_when_no_variants(self) -> None:
        """get_variants_for_axis returns [] for an axis with no registered variants."""
        result = get_variants_for_axis(1)
        assert result == []

    def test_returns_only_matching_axis(self) -> None:
        """get_variants_for_axis filters to the requested axis."""
        register_variant(_DummyVariantAxis1)
        register_variant(_DummyVariantAxis3)

        axis1 = get_variants_for_axis(1)
        axis3 = get_variants_for_axis(3)

        assert len(axis1) == 1
        assert axis1[0].metadata().name == "dummy-axis1"
        assert len(axis3) == 1
        assert axis3[0].metadata().name == "dummy-axis3"

    def test_returns_multiple_variants_on_same_axis(self) -> None:
        """get_variants_for_axis returns all variants registered on an axis."""
        register_variant(_DummyVariantAxis1)
        register_variant(_DummyVariantAxis1B)

        axis1 = get_variants_for_axis(1)
        assert len(axis1) == 2
        names = {v.metadata().name for v in axis1}
        assert names == {"dummy-axis1", "dummy-axis1b"}

    def test_returns_empty_for_unregistered_axis(self) -> None:
        """get_variants_for_axis returns [] for an axis with no variants."""
        register_variant(_DummyVariantAxis1)
        result = get_variants_for_axis(7)
        assert result == []


# ---------------------------------------------------------------------------
# Registry: get_all_variants tests
# ---------------------------------------------------------------------------


class TestGetAllVariants:
    """Tests for get_all_variants."""

    def test_returns_empty_when_nothing_registered(self) -> None:
        """get_all_variants returns [] when no variants have been registered."""
        assert get_all_variants() == []

    def test_returns_all_registered_variants(self) -> None:
        """get_all_variants returns every registered variant."""
        register_variant(_DummyVariantAxis1)
        register_variant(_DummyVariantAxis1B)
        register_variant(_DummyVariantAxis3)

        all_v = get_all_variants()
        assert len(all_v) == 3
        names = {v.metadata().name for v in all_v}
        assert names == {"dummy-axis1", "dummy-axis1b", "dummy-axis3"}
