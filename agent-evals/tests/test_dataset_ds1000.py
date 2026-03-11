"""Tests for the DS-1000 dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


def _make_ds1000_record(
    prompt: str = "import numpy as np\ndef solve():\n    # ",
    reference_code: str = "return np.array([1,2,3])",
    code_context: str = "import numpy as np",
    library: str = "numpy",
    docs: list[dict] | None = None,
) -> dict:
    if docs is None:
        docs = [{"title": "numpy.array", "text": "Create an array.", "function": "numpy.array"}]
    return {
        "prompt": prompt,
        "reference_code": reference_code,
        "code_context": code_context,
        "metadata": {
            "problem_id": 0,
            "library_problem_id": 0,
            "library": library,
            "test_case_cnt": 1,
            "perturbation_type": "Origin",
            "perturbation_origin_id": 0,
        },
        "docs": docs,
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestDS1000Metadata:
    def test_name(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().name() == "ds1000"

    def test_task_type(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().task_type() == "code_generation"

    def test_domain(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().domain() == "library_docs"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().contamination_risk() == "moderate"


class TestDS1000ConvertTasks:
    def test_converts_records_to_code_generation_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(),
            _make_ds1000_record(library="pandas"),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(
                prompt="import numpy\ndef solve(): ...",
                reference_code="def g(df, List):\n    return df.iloc[List]\n\nresult = g(df.copy(), List)",
            ),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("ds1000_code_generation_")
        assert task["type"] == "code_generation"
        assert task["domain"] == "library_docs"
        assert "test" in task["metadata"]
        assert "canonical_solution" in task["metadata"]
        assert "forbidden_patterns" in task["metadata"]

    def test_test_field_contains_extracted_patterns_not_raw_ref_code(self, tmp_path: Path) -> None:
        """Bug #169: test field should contain extracted patterns, not raw reference_code."""
        from agent_evals.datasets.ds1000 import DS1000Adapter

        ref_code = "def g(df, List):\n    return df.iloc[List]\n\nresult = g(df.copy(), List)"
        records = [_make_ds1000_record(reference_code=ref_code)]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))

        test_field = task["metadata"]["test"]
        # Should NOT contain the full wrapper function definition
        assert "def g(df, List):" not in test_field
        # Should contain the key expression
        assert "df.iloc[List]" in test_field
        # canonical_solution should still have the full code
        assert task["metadata"]["canonical_solution"] == ref_code

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [_make_ds1000_record() for _ in range(20)]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5


class TestDS1000BuildDocTree:
    def test_builds_doc_tree(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(
                docs=[{"title": "numpy.array", "text": "Create an array.", "function": "numpy.array"}],
            ),
            _make_ds1000_record(
                docs=[{"title": "pandas.DataFrame", "text": "2D data structure.", "function": "pandas.DataFrame"}],
            ),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) == 2


class TestExtractKeyPatternsTopLevelAssignment:
    """Bug #185: _extract_key_patterns returns empty for top-level assignment solutions."""

    def test_extracts_from_top_level_assignment(self) -> None:
        """Top-level `result = expr` should extract the RHS expression."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "result = df.groupby('col').mean()"
        patterns = _extract_key_patterns(code)
        assert len(patterns) > 0
        assert any("groupby" in p for p in patterns)

    def test_extracts_function_calls_from_assignment_rhs(self) -> None:
        """Assignment RHS with function calls should yield patterns."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "result = np.concatenate([a, b], axis=0)"
        patterns = _extract_key_patterns(code)
        assert len(patterns) > 0
        assert any("concatenate" in p for p in patterns)

    def test_extracts_from_bare_assignment_no_function_def(self) -> None:
        """Code with just an assignment (no function) should not return empty."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "result = pd.merge(df1, df2, on='key')"
        patterns = _extract_key_patterns(code)
        assert len(patterns) > 0
        assert any("merge" in p for p in patterns)


class TestDS1000Registration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.ds1000  # noqa: F401

        assert "ds1000" in DATASET_REGISTRY


# ---------------------------------------------------------------------------
# Bug #169: _extract_key_patterns tests
# ---------------------------------------------------------------------------


class TestExtractKeyPatterns:
    """Tests for _extract_key_patterns which extracts scorable patterns from reference code."""

    def test_extracts_return_expression_from_simple_function(self) -> None:
        """Extracts the return expression from a simple wrapper function."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "def g(df, List):\n    return df.iloc[List]\n\nresult = g(df.copy(), List)"
        patterns = _extract_key_patterns(code)
        assert "df.iloc[List]" in patterns

    def test_extracts_from_numpy_reference(self) -> None:
        """Extracts patterns from numpy-style reference code."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "def g(arr):\n    return np.sort(arr)[::-1]\n\nresult = g(arr)"
        patterns = _extract_key_patterns(code)
        assert any("np.sort" in p for p in patterns)

    def test_extracts_from_multiline_function_body(self) -> None:
        """Extracts patterns from a function with multiple statements."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "def g(df):\n    df = df.dropna()\n    return df.groupby('col').mean()"
        patterns = _extract_key_patterns(code)
        # Should get the return expression at minimum
        assert any("groupby" in p for p in patterns)

    def test_returns_empty_list_for_empty_code(self) -> None:
        """Returns empty list for empty reference code."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        assert _extract_key_patterns("") == []

    def test_heuristic_fallback_for_unparseable_code(self) -> None:
        """Falls back to heuristic extraction when AST parsing fails."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        # Code that won't parse (incomplete/invalid syntax)
        code = "return df.iloc[List]\nresult = g(df.copy()"
        patterns = _extract_key_patterns(code)
        assert any("df.iloc[List]" in p for p in patterns)

    def test_filters_out_boilerplate(self) -> None:
        """Heuristic extraction filters out function defs and result assignments."""
        from agent_evals.datasets.ds1000 import _extract_patterns_heuristic

        code = "def g(df, List):\n    return df.iloc[List]\n\nresult = g(df.copy(), List)"
        patterns = _extract_patterns_heuristic(code)
        # Should not include "def g(..." or "result = ..."
        assert not any(p.startswith("def ") for p in patterns)
        assert not any(p.startswith("result ") for p in patterns)
        # Should include the return expression
        assert "df.iloc[List]" in patterns

    def test_no_duplicate_patterns(self) -> None:
        """Extracted patterns should be meaningful, not duplicated."""
        from agent_evals.datasets.ds1000 import _extract_key_patterns

        code = "def g(x):\n    return x + 1\n\nresult = g(5)"
        patterns = _extract_key_patterns(code)
        assert len(patterns) == len(set(patterns))
