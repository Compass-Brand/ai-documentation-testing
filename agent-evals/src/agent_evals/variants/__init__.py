"""Variant system for index format experimentation.

Public API:
    - ``VariantMetadata`` -- Pydantic model describing a variant.
    - ``IndexVariant`` -- ABC that all variants must subclass.
    - ``register_variant`` -- Register a variant class (also usable as decorator).
    - ``get_all_variants`` -- Retrieve every registered variant instance.
    - ``get_variants_for_axis`` -- Retrieve variants for a specific eval axis.
    - ``load_all`` -- Auto-discover variant modules via pkgutil.
"""

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    load_all,
    register_variant,
)

__all__ = [
    "IndexVariant",
    "VariantMetadata",
    "clear_registry",
    "get_all_variants",
    "get_variants_for_axis",
    "load_all",
    "register_variant",
]
