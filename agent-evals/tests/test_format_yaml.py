"""Tests for the YAML format variant."""

import yaml

from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.variants.format_yaml import FormatYaml
from agent_index.models import DocTree


def make_doc_tree(summary: str = "test summary") -> DocTree:
    """Return a DocTree with the first file's summary set for testing.

    render() takes DocTree NOT list[DocFile] — always pass the full DocTree.
    """
    doc_tree = load_sample_doc_tree()
    doc = next(iter(doc_tree.files.values()))
    doc.summary = summary
    return doc_tree


def test_yaml_summary_with_colon_is_parseable():
    variant = FormatYaml()
    doc_tree = make_doc_tree(summary="JWT auth: token-based login")
    output = variant.render(doc_tree)
    parsed = yaml.safe_load(output)  # Must not raise ScannerError
    assert parsed is not None
