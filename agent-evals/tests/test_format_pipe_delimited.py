"""Tests for the pipe-delimited format variant."""

import re

from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.variants.format_pipe_delimited import FormatPipeDelimited
from agent_index.models import DocTree


def make_doc_tree(summary: str = "test summary") -> DocTree:
    """Return a DocTree with the first file's summary set for testing.

    render() takes DocTree NOT list[DocFile] — always pass the full DocTree.
    """
    doc_tree = load_sample_doc_tree()
    doc = next(iter(doc_tree.files.values()))
    doc.summary = summary
    return doc_tree


# Header: "path|section|tier|tokens|summary" = 5 columns
EXPECTED_COLUMN_COUNT = 5


def test_pipe_in_summary_does_not_add_extra_columns():
    variant = FormatPipeDelimited()
    doc_tree = make_doc_tree(summary="A|B comparison")
    output = variant.render(doc_tree)
    data_rows = [r for r in output.splitlines() if "comparison" in r]
    assert len(data_rows) == 1
    # Split on unescaped pipes only (pipes NOT preceded by backslash)
    columns = re.split(r"(?<!\\)\|", data_rows[0])
    assert len(columns) == EXPECTED_COLUMN_COUNT
    # Verify the summary column contains the original text (unescaped)
    assert columns[-1].replace("\\|", "|") == "A|B comparison"
