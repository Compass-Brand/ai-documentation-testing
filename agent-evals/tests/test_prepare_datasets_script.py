"""Tests for scripts/prepare-datasets.sh existence and structure."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "prepare-datasets.sh"
)


class TestPrepareDatasetScript:
    """Verify the script exists and has expected properties."""

    def test_script_exists(self) -> None:
        assert SCRIPT.is_file(), f"Script not found: {SCRIPT}"

    def test_script_is_executable(self) -> None:
        assert os.access(SCRIPT, os.X_OK), "Script is not executable"

    def test_script_has_shebang(self) -> None:
        first_line = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("#!/"), "Missing shebang line"

    def test_script_uses_set_euo_pipefail(self) -> None:
        content = SCRIPT.read_text(encoding="utf-8")
        assert "set -euo pipefail" in content

    def test_script_supports_single_dataset_arg(self) -> None:
        content = SCRIPT.read_text(encoding="utf-8")
        assert "DATASETS=" in content or "datasets" in content.lower()

    def test_script_supports_cache_dir_env(self) -> None:
        content = SCRIPT.read_text(encoding="utf-8")
        assert "DATASET_CACHE_DIR" in content

    def test_script_calls_prepare_datasets_flag(self) -> None:
        content = SCRIPT.read_text(encoding="utf-8")
        assert "--prepare-datasets" in content
