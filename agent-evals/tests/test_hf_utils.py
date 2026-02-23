"""Tests for HuggingFace utility helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import error handling
# ---------------------------------------------------------------------------


class TestHFImportError:
    """Test graceful handling when datasets library is not installed."""

    def test_missing_datasets_library_raises_import_error(self) -> None:
        """When 'datasets' is not installed, a clear error message is raised."""
        from agent_evals.datasets._hf_utils import load_hf_dataset

        with patch.dict("sys.modules", {"datasets": None}):
            with pytest.raises(ImportError, match="HuggingFace datasets library"):
                load_hf_dataset("org/dataset", split="test")


# ---------------------------------------------------------------------------
# load_hf_dataset with mocked HF
# ---------------------------------------------------------------------------


class TestLoadHFDataset:
    """Tests for load_hf_dataset with mocked HuggingFace calls."""

    def test_loads_dataset_with_correct_args(self) -> None:
        """Calls load_dataset with the right dataset_id and split."""
        from agent_evals.datasets._hf_utils import load_hf_dataset

        mock_ds = MagicMock()
        mock_ds.__len__ = lambda self: 100

        with patch("agent_evals.datasets._hf_utils._import_load_dataset") as mock_import:
            mock_import.return_value = lambda *a, **kw: mock_ds
            result = load_hf_dataset("org/dataset", split="train")

        assert result is mock_ds

    def test_limit_parameter_selects_subset(self) -> None:
        """When limit is set, only that many items are selected."""
        from agent_evals.datasets._hf_utils import load_hf_dataset

        mock_ds = MagicMock()
        mock_ds.__len__ = lambda self: 1000
        mock_ds.select = MagicMock(return_value="subset")

        with patch("agent_evals.datasets._hf_utils._import_load_dataset") as mock_import:
            mock_import.return_value = lambda *a, **kw: mock_ds
            result = load_hf_dataset("org/dataset", split="train", limit=50)

        mock_ds.select.assert_called_once()
        call_args = mock_ds.select.call_args[0][0]
        assert len(call_args) == 50

    def test_limit_larger_than_dataset_uses_full_dataset(self) -> None:
        """When limit exceeds dataset size, use full dataset."""
        from agent_evals.datasets._hf_utils import load_hf_dataset

        mock_ds = MagicMock()
        mock_ds.__len__ = lambda self: 10
        mock_ds.select = MagicMock(return_value="subset")

        with patch("agent_evals.datasets._hf_utils._import_load_dataset") as mock_import:
            mock_import.return_value = lambda *a, **kw: mock_ds
            result = load_hf_dataset("org/dataset", split="train", limit=500)

        mock_ds.select.assert_called_once()
        call_args = mock_ds.select.call_args[0][0]
        assert len(call_args) == 10  # min(500, 10) = 10

    def test_no_limit_returns_full_dataset(self) -> None:
        """When limit is None, the full dataset is returned."""
        from agent_evals.datasets._hf_utils import load_hf_dataset

        mock_ds = MagicMock()
        mock_ds.__len__ = lambda self: 100

        with patch("agent_evals.datasets._hf_utils._import_load_dataset") as mock_import:
            mock_import.return_value = lambda *a, **kw: mock_ds
            result = load_hf_dataset("org/dataset", split="train", limit=None)

        mock_ds.select.assert_not_called()
        assert result is mock_ds
