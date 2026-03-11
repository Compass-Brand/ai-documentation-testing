"""Tests for the RetrievalTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: perfect match (1.0)
- score_response: no match (0.0)
- score_response: partial match (between 0 and 1)
- F-beta scoring favors recall over precision
- Edge cases: empty expected_files, various file path formats
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.retrieval import RetrievalTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retrieval_task(**meta_overrides: Any) -> RetrievalTask:
    """Create a RetrievalTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_files": ["src/auth.py", "docs/auth.md"],
        "evidence_passage": "The auth middleware validates JWT tokens.",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="retrieval_001",
        type="retrieval",
        question="Which files handle authentication?",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return RetrievalTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestRetrievalTaskConstruction:
    """Tests for RetrievalTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """RetrievalTask accepts a TaskDefinition with valid metadata."""
        task = _retrieval_task()
        assert task.expected_files == ["src/auth.py", "docs/auth.md"]
        assert task.evidence_passage == "The auth middleware validates JWT tokens."

    def test_defaults_for_missing_metadata(self) -> None:
        """RetrievalTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="retrieval_002",
            type="retrieval",
            question="Find files",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = RetrievalTask(defn)
        assert task.expected_files == []
        assert task.evidence_passage == ""

    def test_registered_in_task_types(self) -> None:
        """RetrievalTask is registered in TASK_TYPES for 'retrieval'."""
        assert TASK_TYPES["retrieval"] is RetrievalTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestRetrievalTaskBuildPrompt:
    """Tests for RetrievalTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _retrieval_task()
        messages = task.build_prompt("# Index\n- src/auth.py\n- docs/auth.md")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _retrieval_task()
        messages = task.build_prompt("MY_UNIQUE_INDEX_CONTENT")
        all_content = " ".join(m["content"] for m in messages)
        assert "MY_UNIQUE_INDEX_CONTENT" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _retrieval_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Which files handle authentication?" in all_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestRetrievalTaskScoring:
    """Tests for RetrievalTask.score_response (F-beta with beta=2)."""

    def test_perfect_match_returns_1(self) -> None:
        """Response mentioning all expected files and no extras scores 1.0."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "The relevant files are src/auth.py and docs/auth.md."
        score = task.score_response(response)
        assert score == 1.0

    def test_no_match_returns_0(self) -> None:
        """Response mentioning no expected files scores 0.0."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "I don't know which files are relevant."
        score = task.score_response(response)
        assert score == 0.0

    def test_partial_recall_scores_between_0_and_1(self) -> None:
        """Response mentioning some but not all expected files scores partially."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "The relevant file is src/auth.py."
        score = task.score_response(response)
        assert 0.0 < score < 1.0

    def test_fbeta_favors_recall_over_precision(self) -> None:
        """F-beta(2) gives higher score to high-recall result than high-precision result.

        High recall: finds 2/2 expected but includes 2 extras (recall=1.0, precision=0.5)
        High precision: finds 1/2 expected, no extras (recall=0.5, precision=1.0)
        With beta=2, recall matters more, so high-recall should score higher.
        """
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])

        # High recall: mentions both expected + extras
        high_recall_response = (
            "Files: src/auth.py, docs/auth.md, src/utils.py, config/settings.yaml"
        )
        # High precision: mentions 1 expected, no extras
        high_precision_response = "File: src/auth.py"

        recall_score = task.score_response(high_recall_response)
        precision_score = task.score_response(high_precision_response)

        assert recall_score > precision_score

    def test_empty_expected_files_returns_1_for_empty_response(self) -> None:
        """When no files are expected and none found, score is 1.0 (vacuous truth)."""
        task = _retrieval_task(expected_files=[])
        score = task.score_response("No files are relevant.")
        assert score == 1.0

    def test_empty_expected_files_returns_0_when_files_found(self) -> None:
        """When no files are expected but files are found, score is 0.0."""
        task = _retrieval_task(expected_files=[])
        score = task.score_response("Check src/auth.py for details.")
        assert score == 0.0

    def test_extracts_various_file_extensions(self) -> None:
        """score_response extracts paths with various common extensions."""
        task = _retrieval_task(
            expected_files=[
                "src/config.yaml",
                "docs/README.md",
                "tests/test_auth.py",
            ]
        )
        response = (
            "Look at src/config.yaml for configuration, "
            "docs/README.md for docs, and tests/test_auth.py for tests."
        )
        score = task.score_response(response)
        assert score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _retrieval_task(expected_files=["src/auth.py"])
        for resp in ["src/auth.py", "nothing here", "src/auth.py extra.py"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Step 3.9: Path normalization and fuzzy matching
# ---------------------------------------------------------------------------


class TestRetrievalPathNormalization:
    """Tests for path normalization in retrieval scoring."""

    def test_case_insensitive_path_matching(self) -> None:
        """File path matching is case-insensitive."""
        task = _retrieval_task(expected_files=["src/Auth.py", "docs/README.md"])
        response = "Look at SRC/AUTH.PY and DOCS/README.MD."
        score = task.score_response(response)
        assert score == 1.0

    def test_leading_dot_slash_normalized(self) -> None:
        """Paths with leading ./ match paths without it."""
        task = _retrieval_task(expected_files=["./src/auth.py"])
        response = "The file is src/auth.py."
        score = task.score_response(response)
        assert score > 0.0

    def test_trailing_slash_normalized(self) -> None:
        """Trailing slashes are ignored when matching."""
        task = _retrieval_task(expected_files=["src/auth.py"])
        response = "Check ./src/auth.py for the details."
        score = task.score_response(response)
        assert score > 0.0

    def test_partial_credit_for_close_match(self) -> None:
        """Partial credit when response has close but not exact path matches.

        Tests that similar file paths (e.g. basename match) contribute
        some score rather than 0.0.
        """
        task = _retrieval_task(expected_files=["src/auth.py"])
        # Response mentions the file but in a different path
        response = "The authentication code is in lib/auth.py."
        score = task.score_response(response)
        # Should get some partial credit via fuzzy matching
        assert score > 0.0

    def test_fuzzy_match_does_not_reuse_extracted_path(self) -> None:
        """Same extracted path must not fuzzy-match multiple expected files.

        Bug #138: After a fuzzy basename match, the matched extracted path
        was not removed from the candidate set, allowing one extracted path
        to match two or more expected paths and inflate the score above 1.0.
        """
        # Two expected files share the same basename but different dirs
        task = _retrieval_task(
            expected_files=["src/auth.py", "lib/auth.py"],
        )
        # Response only mentions ONE path with that basename in a THIRD dir
        response = "Check vendor/auth.py for details."
        score = task.score_response(response)
        # Only one extracted file, so it can match at most one expected file.
        # Score must not exceed 1.0 and must reflect partial recall.
        assert score <= 1.0
        # With 2 expected and only 1 fuzzy match (0.5 true positives),
        # recall = 0.5 / 2 = 0.25, precision = 0.5 / 1 = 0.5
        # F-beta(2) = 5 * 0.5 * 0.25 / (4 * 0.5 + 0.25) = 0.625 / 2.25 ~ 0.278
        # Before the fix, fuzzy_hits would be 1.0 (0.5 + 0.5) since
        # the same extracted path matched both expected files.
        assert score < 0.5, (
            f"Score {score} is too high; same extracted path likely matched "
            f"multiple expected files (bug #138)"
        )


# ---------------------------------------------------------------------------
# Bug #144: _FILE_PATH_PATTERN missing many common extensions
# ---------------------------------------------------------------------------


class TestRetrievalExtractionBroadExtensions:
    """Bug #144: _FILE_PATH_PATTERN should match common programming extensions.

    The original pattern only matched 8 extensions (md|py|yaml|yml|json|toml|
    txt|rst|html). It must also match ts, tsx, js, jsx, css, scss, go, rs,
    java, xml, cfg, ini, sh, bash, dockerfile, rb, php, c, cpp, h, and more.
    """

    def test_extracts_typescript_files(self) -> None:
        """Pattern matches .ts and .tsx file extensions."""
        task = _retrieval_task(expected_files=["src/app.ts", "src/App.tsx"])
        response = "Check src/app.ts and src/App.tsx for the component."
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_javascript_files(self) -> None:
        """Pattern matches .js and .jsx file extensions."""
        task = _retrieval_task(expected_files=["src/index.js", "src/App.jsx"])
        response = "Look at src/index.js and src/App.jsx."
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_css_files(self) -> None:
        """Pattern matches .css and .scss file extensions."""
        task = _retrieval_task(expected_files=["styles/main.css", "styles/theme.scss"])
        response = "Styles are in styles/main.css and styles/theme.scss."
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_systems_language_files(self) -> None:
        """Pattern matches .go, .rs, .java, .c, .cpp, .h file extensions."""
        task = _retrieval_task(
            expected_files=[
                "pkg/server.go",
                "src/lib.rs",
                "src/Main.java",
                "src/core.c",
                "src/engine.cpp",
                "include/header.h",
            ]
        )
        response = (
            "See pkg/server.go, src/lib.rs, src/Main.java, "
            "src/core.c, src/engine.cpp, and include/header.h."
        )
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_config_files(self) -> None:
        """Pattern matches .xml, .cfg, .ini file extensions."""
        task = _retrieval_task(
            expected_files=["config/app.xml", "config/settings.cfg", "config/db.ini"]
        )
        response = "Config in config/app.xml, config/settings.cfg, config/db.ini."
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_shell_files(self) -> None:
        """Pattern matches .sh and .bash file extensions."""
        task = _retrieval_task(expected_files=["scripts/deploy.sh", "scripts/build.bash"])
        response = "Run scripts/deploy.sh and scripts/build.bash."
        score = task.score_response(response)
        assert score == 1.0

    def test_extracts_scripting_language_files(self) -> None:
        """Pattern matches .rb and .php file extensions."""
        task = _retrieval_task(expected_files=["app/models/user.rb", "src/api.php"])
        response = "See app/models/user.rb and src/api.php."
        score = task.score_response(response)
        assert score == 1.0

    def test_still_extracts_original_extensions(self) -> None:
        """Original 8 extensions still work after the fix."""
        task = _retrieval_task(
            expected_files=[
                "docs/README.md",
                "src/main.py",
                "config.yaml",
                "config.yml",
                "data.json",
                "settings.toml",
                "notes.txt",
                "guide.rst",
            ]
        )
        response = (
            "docs/README.md src/main.py config.yaml config.yml "
            "data.json settings.toml notes.txt guide.rst"
        )
        score = task.score_response(response)
        assert score == 1.0


# ---------------------------------------------------------------------------
# Suffix matching for multi-source merged doc trees
# ---------------------------------------------------------------------------


class TestRetrievalSuffixMatching:
    """Tests for suffix matching when multi-source merging prefixes paths."""

    def test_dataset_prefixed_path_matches_expected(self) -> None:
        """Response with dataset-prefixed path matches unprefixed expected file."""
        task = _retrieval_task(
            expected_files=["library-docs/has_close_elements.md"],
        )
        response = "The relevant file is code-rag-bench/library-docs/has_close_elements.md."
        score = task.score_response(response)
        assert score == 1.0

    def test_suffix_match_counts_as_exact(self) -> None:
        """Suffix match gives full credit, not partial (0.5) fuzzy credit."""
        task = _retrieval_task(
            expected_files=["src/auth.py"],
        )
        response = "Check dataset-name/src/auth.py for details."
        score = task.score_response(response)
        assert score == 1.0


# ---------------------------------------------------------------------------
# Bug #203: version numbers matched as false file paths
# ---------------------------------------------------------------------------


class TestBug203VersionNumberFalsePositives:
    """Bug #203: regex matches version strings like v2.2.0 as file paths."""

    def test_version_number_not_extracted_as_file_path(self) -> None:
        """Version strings like v2.2.0 should not be treated as file paths."""
        from agent_evals.tasks.retrieval import _FILE_PATH_PATTERN

        matches = _FILE_PATH_PATTERN.findall("Updated to v2.2.0 in the latest release")
        file_like = [m for m in matches if not m.startswith("v") or "/" in m]
        assert len(file_like) == 0, (
            f"Version string matched as file path: {matches}"
        )

    def test_version_in_sentence_does_not_inflate_score(self) -> None:
        """Responses mentioning versions should not get false positive file matches."""
        task = _retrieval_task(expected_files=[])
        response = "This was fixed in v2.2.0 and v3.1.0-beta.1 of the framework."
        score = task.score_response(response)
        # No expected files and no real files extracted -> 1.0
        # If version strings are extracted as files, score would be 0.0
        assert score == 1.0

    def test_real_file_paths_still_extracted(self) -> None:
        """Paths with slashes or proper extensions are still recognized."""
        from agent_evals.tasks.retrieval import _FILE_PATH_PATTERN

        text = "See src/config.yaml and lib/utils.py for v2.2.0 changes"
        matches = _FILE_PATH_PATTERN.findall(text)
        paths = {m for m in matches}
        assert "src/config.yaml" in paths
        assert "lib/utils.py" in paths
