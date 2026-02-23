"""HuggingFace helper utilities with lazy import.

The ``datasets`` library is only imported when actually needed,
keeping the core agent-evals package free of heavy dependencies.
"""

from __future__ import annotations

from typing import Any, Callable


def _import_load_dataset() -> Callable[..., Any]:
    """Import and return the HF ``load_dataset`` function.

    Raises:
        ImportError: With a clear message if the library is missing.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        msg = (
            "HuggingFace datasets library required. "
            "Install with: uv add --optional datasets 'datasets>=2.14'"
        )
        raise ImportError(msg)
    return load_dataset


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
    load_dataset = _import_load_dataset()
    ds = load_dataset(dataset_id, split=split, trust_remote_code=False, **kwargs)
    if limit is not None:
        ds = ds.select(range(min(limit, len(ds))))
    return ds
