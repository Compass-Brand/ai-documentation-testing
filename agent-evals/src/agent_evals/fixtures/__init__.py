"""Fixture loaders for sample documentation used in evaluation tests."""

from __future__ import annotations

import json
from pathlib import Path

from agent_index.models import DocTree

_FIXTURES_DIR = Path(__file__).resolve().parent
_DOC_TREE_JSON = _FIXTURES_DIR / "doc_tree.json"
_SAMPLE_DOCS_DIR = _FIXTURES_DIR / "sample_docs"


def load_sample_doc_tree() -> DocTree:
    """Load the sample documentation tree fixture.

    Reads ``doc_tree.json`` from the fixtures directory and returns a fully
    populated :class:`~agent_index.models.DocTree` instance whose files
    contain realistic synthetic documentation content.
    """
    raw = _DOC_TREE_JSON.read_text(encoding="utf-8")
    data = json.loads(raw)
    return DocTree.model_validate(data)


def sample_docs_directory() -> Path:
    """Return the path to the ``sample_docs/`` directory on disk."""
    return _SAMPLE_DOCS_DIR
