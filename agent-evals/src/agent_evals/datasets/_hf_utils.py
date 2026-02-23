"""HuggingFace helper utilities.

Provides a thin wrapper around ``datasets.load_dataset`` with an
optional ``limit`` parameter for cost-controlled data loading.
"""

from __future__ import annotations

from typing import Any

from datasets import load_dataset


def load_hf_dataset(
    dataset_id: str,
    split: str,
    limit: int | None = None,
    **kwargs: Any,
) -> Any:
    """Load a HuggingFace dataset with optional limit.

    Args:
        dataset_id: HuggingFace dataset identifier (e.g. 'org/name').
        split: Dataset split to load (e.g. 'train', 'test').
        limit: Maximum number of records to return.
        **kwargs: Extra keyword arguments passed to ``load_dataset``.

    Returns:
        A HuggingFace Dataset object (or subset if limit is set).
    """
    ds = load_dataset(dataset_id, split=split, trust_remote_code=False, **kwargs)
    if limit is not None:
        ds = ds.select(range(min(limit, len(ds))))
    return ds
