"""Tests for GitHub repository scanner functionality."""

import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_index.models import DocTree
from agent_index.scanner import GitHubError, _github_api_get, scan_github


class TestScanGitHubValidation:
    """Tests for input validation."""

    def test_invalid_repo_format_no_slash(self) -> None:
        """scan_github raises ValueError for repo without slash."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            scan_github("invalid-repo")

    def test_invalid_repo_format_empty_owner(self) -> None:
        """scan_github raises ValueError for empty owner."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            scan_github("/repo")

    def test_invalid_repo_format_empty_repo(self) -> None:
        """scan_github raises ValueError for empty repo name."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            scan_github("owner/")

    def test_invalid_repo_format_too_many_slashes(self) -> None:
        """scan_github raises ValueError for too many slashes."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            scan_github("owner/repo/extra")


class TestScanGitHubBasic:
    """Basic tests for scan_github function."""

    def test_returns_doctree(self, mock_github_api: MagicMock) -> None:
        """scan_github returns a DocTree instance."""
        mock_github_api.return_value = self._make_response([
            {"name": "README.md", "type": "file", "path": "README.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Hello"):
            result = scan_github("owner/repo")

        assert isinstance(result, DocTree)

    def test_doctree_has_source(self, mock_github_api: MagicMock) -> None:
        """DocTree source indicates GitHub repo."""
        mock_github_api.return_value = self._make_response([
            {"name": "README.md", "type": "file", "path": "README.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Hello"):
            result = scan_github("owner/repo")

        assert result.source == "github:owner/repo"

    def test_doctree_has_scanned_at(self, mock_github_api: MagicMock) -> None:
        """DocTree has scanned_at timestamp."""
        mock_github_api.return_value = self._make_response([
            {"name": "README.md", "type": "file", "path": "README.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Hello"):
            result = scan_github("owner/repo")

        assert isinstance(result.scanned_at, datetime)
        assert (datetime.now(UTC) - result.scanned_at).total_seconds() < 60

    def test_finds_markdown_file(self, mock_github_api: MagicMock, tmp_path: Path) -> None:
        """scan_github finds markdown files."""
        mock_github_api.return_value = self._make_response([
            {"name": "README.md", "type": "file", "path": "README.md", "sha": "unique_sha_1"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Hello World"):
            result = scan_github("owner/repo", cache_dir=tmp_path)

        assert "README.md" in result.files
        assert result.files["README.md"].content == "# Hello World"

    def test_docfile_has_content_hash(self, mock_github_api: MagicMock) -> None:
        """DocFile includes content hash."""
        mock_github_api.return_value = self._make_response([
            {"name": "test.md", "type": "file", "path": "test.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        hash_value = result.files["test.md"].content_hash
        assert len(hash_value) == 64  # SHA-256
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_docfile_tier_and_section_initially_empty(self, mock_github_api: MagicMock) -> None:
        """DocFile.tier and DocFile.section are empty string initially."""
        mock_github_api.return_value = self._make_response([
            {"name": "test.md", "type": "file", "path": "test.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        doc = result.files["test.md"]
        assert doc.tier == ""
        assert doc.section == ""

    @staticmethod
    def _make_response(data: list) -> MagicMock:
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {}
        return response


class TestScanGitHubRecursive:
    """Tests for recursive directory scanning."""

    def test_scans_subdirectories(self, mock_github_api: MagicMock) -> None:
        """scan_github scans subdirectories recursively."""
        # Root directory response
        root_response = MagicMock()
        root_response.status_code = 200
        root_response.json.return_value = [
            {"name": "README.md", "type": "file", "path": "README.md", "sha": "abc1"},
            {"name": "docs", "type": "dir", "path": "docs"}
        ]
        root_response.headers = {}

        # Subdirectory response
        docs_response = MagicMock()
        docs_response.status_code = 200
        docs_response.json.return_value = [
            {"name": "guide.md", "type": "file", "path": "docs/guide.md", "sha": "abc2"}
        ]
        docs_response.headers = {}

        # Return different responses for different URLs
        def get_response(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "contents/docs" in url:
                return docs_response
            return root_response

        mock_github_api.side_effect = get_response

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        assert "README.md" in result.files
        assert "docs/guide.md" in result.files


class TestScanGitHubFileExtensions:
    """Tests for file extension filtering."""

    def test_default_extensions_md(self, mock_github_api: MagicMock) -> None:
        """scan_github includes .md files by default."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        assert "readme.md" in result.files

    def test_excludes_non_matching_extensions(self, mock_github_api: MagicMock) -> None:
        """scan_github excludes files with non-matching extensions."""
        mock_github_api.return_value = self._make_response([
            {"name": "script.py", "type": "file", "path": "script.py", "sha": "abc1"},
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc2"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        assert "script.py" not in result.files
        assert "readme.md" in result.files

    def test_custom_file_extensions(self, mock_github_api: MagicMock) -> None:
        """scan_github respects custom file_extensions."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc1"},
            {"name": "script.py", "type": "file", "path": "script.py", "sha": "abc2"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo", file_extensions={".py"})

        assert "script.py" in result.files
        assert "readme.md" not in result.files

    @staticmethod
    def _make_response(data: list) -> MagicMock:
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {}
        return response


class TestScanGitHubIgnorePatterns:
    """Tests for ignore pattern filtering."""

    def test_default_ignores_node_modules(self, mock_github_api: MagicMock) -> None:
        """scan_github ignores node_modules by default."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc1"},
            {"name": "node_modules", "type": "dir", "path": "node_modules"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo")

        assert "readme.md" in result.files
        # Should not have traversed into node_modules
        assert mock_github_api.call_count == 1

    def test_custom_ignore_patterns(self, mock_github_api: MagicMock) -> None:
        """scan_github respects custom ignore_patterns."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc1"},
            {"name": "build", "type": "dir", "path": "build"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            result = scan_github("owner/repo", ignore_patterns=["build"])

        assert "readme.md" in result.files
        # Should not have traversed into build
        assert mock_github_api.call_count == 1

    @staticmethod
    def _make_response(data: list) -> MagicMock:
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {}
        return response


class TestScanGitHubBranchAndPath:
    """Tests for branch and path parameters."""

    def test_uses_specified_branch(self, mock_github_api: MagicMock) -> None:
        """scan_github uses the specified branch."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            scan_github("owner/repo", branch="develop")

        call_url = mock_github_api.call_args[0][0]
        assert "ref=develop" in call_url

    def test_uses_specified_path(self, mock_github_api: MagicMock) -> None:
        """scan_github scans from the specified path."""
        mock_github_api.return_value = self._make_response([
            {"name": "guide.md", "type": "file", "path": "docs/guide.md", "sha": "abc"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="content"):
            scan_github("owner/repo", path="docs")

        call_url = mock_github_api.call_args[0][0]
        assert "/contents/docs" in call_url

    @staticmethod
    def _make_response(data: list) -> MagicMock:
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {}
        return response


class TestScanGitHubCaching:
    """Tests for content caching."""

    def test_caches_fetched_content(self, mock_github_api: MagicMock, tmp_path: Path) -> None:
        """scan_github caches fetched file content."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Cached Content"):
            scan_github("owner/repo", cache_dir=tmp_path)

        # Check cache file exists
        cache_files = list(tmp_path.rglob("*"))
        assert any(f.is_file() for f in cache_files)

    def test_uses_cached_content_on_second_call(self, mock_github_api: MagicMock, tmp_path: Path) -> None:
        """scan_github uses cached content if available."""
        mock_github_api.return_value = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc123"}
        ])

        with patch("agent_index.scanner._fetch_file_content", return_value="# Content") as mock_fetch:
            # First call - fetches content
            scan_github("owner/repo", cache_dir=tmp_path)
            first_call_count = mock_fetch.call_count

            # Second call - should use cache
            scan_github("owner/repo", cache_dir=tmp_path)
            second_call_count = mock_fetch.call_count

        # Content should not be fetched again
        assert second_call_count == first_call_count

    def test_refetches_when_sha_changes(self, mock_github_api: MagicMock, tmp_path: Path) -> None:
        """scan_github refetches content when file sha changes."""
        # First response with sha "abc123"
        first_response = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "abc123"}
        ])
        # Second response with different sha
        second_response = self._make_response([
            {"name": "readme.md", "type": "file", "path": "readme.md", "sha": "def456"}
        ])

        mock_github_api.side_effect = [first_response, second_response]

        with patch("agent_index.scanner._fetch_file_content", return_value="# Content") as mock_fetch:
            # First call
            scan_github("owner/repo", cache_dir=tmp_path)
            first_call_count = mock_fetch.call_count

            # Second call with different sha
            scan_github("owner/repo", cache_dir=tmp_path)
            second_call_count = mock_fetch.call_count

        # Content should be fetched again due to sha change
        assert second_call_count > first_call_count

    @staticmethod
    def _make_response(data: list) -> MagicMock:
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {}
        return response


class TestScanGitHubErrors:
    """Tests for error handling."""

    def test_repo_not_found_raises_github_error(self, mock_github_api: MagicMock) -> None:
        """scan_github raises GitHubError when repo not found."""
        response = MagicMock()
        response.status_code = 404
        response.json.return_value = {"message": "Not Found"}
        response.headers = {}
        mock_github_api.return_value = response

        with pytest.raises(GitHubError) as exc_info:
            scan_github("owner/nonexistent-repo")

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value).lower()

    def test_rate_limit_raises_github_error(self, mock_github_api: MagicMock) -> None:
        """scan_github raises GitHubError when rate limited."""
        response = MagicMock()
        response.status_code = 403
        response.json.return_value = {"message": "API rate limit exceeded"}
        response.headers = {"X-RateLimit-Reset": "1234567890"}
        mock_github_api.return_value = response

        with pytest.raises(GitHubError) as exc_info:
            scan_github("owner/repo")

        assert exc_info.value.status_code == 403
        assert "rate limit" in str(exc_info.value).lower()

    def test_github_error_has_status_code(self, mock_github_api: MagicMock) -> None:
        """GitHubError includes status_code attribute."""
        response = MagicMock()
        response.status_code = 500
        response.json.return_value = {"message": "Internal Server Error"}
        response.headers = {}
        mock_github_api.return_value = response

        with pytest.raises(GitHubError) as exc_info:
            scan_github("owner/repo")

        assert exc_info.value.status_code == 500


class TestGitHubErrorClass:
    """Tests for GitHubError exception class."""

    def test_github_error_message(self) -> None:
        """GitHubError stores message."""
        error = GitHubError("Repository not found")
        assert str(error) == "Repository not found"

    def test_github_error_status_code(self) -> None:
        """GitHubError stores status_code."""
        error = GitHubError("Not found", status_code=404)
        assert error.status_code == 404

    def test_github_error_status_code_default(self) -> None:
        """GitHubError status_code defaults to None."""
        error = GitHubError("Some error")
        assert error.status_code is None


# ---------------------------------------------------------------------------
# Auth and Retry Tests
# ---------------------------------------------------------------------------


class TestGitHubAuth:
    """Tests for GitHub token authentication support."""

    def test_github_token_sent_as_auth_header(self, monkeypatch) -> None:
        """When GITHUB_TOKEN is set, it should be included in API headers."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("agent_index.scanner.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client

            _github_api_get("https://api.github.com/repos/foo/bar/contents")

            # Verify Authorization header was set
            call_kwargs = mock_client.get.call_args
            headers = call_kwargs[1].get("headers", {}) if call_kwargs[1] else call_kwargs.kwargs.get("headers", {})
            assert "Authorization" in headers, "GITHUB_TOKEN should set Authorization header"
            assert headers["Authorization"] == "Bearer ghp_test123"

    def test_no_auth_header_without_token(self, monkeypatch) -> None:
        """When GITHUB_TOKEN is not set, no Authorization header should be sent."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("agent_index.scanner.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client

            _github_api_get("https://api.github.com/repos/foo/bar/contents")

            call_kwargs = mock_client.get.call_args
            headers = call_kwargs[1].get("headers", {}) if call_kwargs[1] else call_kwargs.kwargs.get("headers", {})
            assert "Authorization" not in headers


class TestGitHubRetry:
    """Tests for GitHub API retry with exponential backoff."""

    def test_retries_on_403_rate_limit(self, monkeypatch) -> None:
        """_github_api_get retries on 403 rate limit responses."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.headers = {"X-RateLimit-Remaining": "0"}

        ok_response = MagicMock()
        ok_response.status_code = 200

        with patch("agent_index.scanner.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = [rate_limit_response, ok_response]
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client

            with patch("time.sleep"):  # Don't actually sleep in tests
                result = _github_api_get("https://api.github.com/repos/foo/bar/contents")

            assert result.status_code == 200
            assert mock_client.get.call_count == 2

    def test_retries_on_502_server_error(self, monkeypatch) -> None:
        """_github_api_get retries on 502 server errors."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        error_response = MagicMock()
        error_response.status_code = 502
        error_response.headers = {}

        ok_response = MagicMock()
        ok_response.status_code = 200

        with patch("agent_index.scanner.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.side_effect = [error_response, ok_response]
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client

            with patch("time.sleep"):
                result = _github_api_get("https://api.github.com/repos/foo/bar/contents")

            assert result.status_code == 200

    def test_returns_last_response_after_max_retries(self, monkeypatch) -> None:
        """After max retries, returns the last error response."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        error_response = MagicMock()
        error_response.status_code = 502
        error_response.headers = {}

        with patch("agent_index.scanner.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.get.return_value = error_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client

            with patch("time.sleep"):
                result = _github_api_get(
                    "https://api.github.com/repos/foo/bar/contents",
                    max_retries=3,
                )

            assert result.status_code == 502
            # 1 initial + 3 retries = 4 total calls
            assert mock_client.get.call_count == 4


# Fixtures

@pytest.fixture
def mock_github_api():
    """Mock the GitHub API calls."""
    with patch("agent_index.scanner._github_api_get") as mock:
        yield mock
