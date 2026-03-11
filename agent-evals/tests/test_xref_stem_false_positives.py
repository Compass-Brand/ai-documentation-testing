"""Bug #190: xref_dense stem matching produces false positives for short stems.

The substring check ``stem.lower() in content_lower`` matches partial words:
e.g., stem "api" matches "api_key", stem "auth" matches "authentication".
This inflates cross-reference density artificially.  Stems should match
only at word boundaries.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agent_evals.variants.xref_dense import XrefDenseVariant


def _make_tree_with_short_stems() -> MagicMock:
    """Create a DocTree that exposes the short-stem false-positive bug.

    - ``api.md``: stem "api"
    - ``config.md``: content has "api_key" and "authentication" but NOT
      "api" or "auth" as standalone words
    - ``auth.md``: content has "the api to get" ("api" as standalone word)

    Before the fix:
    - config.md References falsely includes api.md (via "api_key")
    - config.md References falsely includes auth.md (via "authentication")
    """
    tree = MagicMock()
    files: dict[str, MagicMock] = {}

    for path, section, content, summary in [
        (
            "docs/api.md",
            "Reference",
            "Main API documentation for the service endpoints.",
            "API reference docs",
        ),
        (
            "docs/config.md",
            "Reference",
            "Configuration uses api_key and api_token for authentication.",
            "Configuration reference",
        ),
        (
            "docs/auth.md",
            "Reference",
            "Authentication module. Call the api to get a token.",
            "Auth module docs",
        ),
    ]:
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.section = section
        doc.summary = summary
        files[path] = doc

    tree.files = files
    return tree


def _get_sub_lines(lines: list[str], file_prefix: str) -> dict[str, str]:
    """Extract See-also and References lines for a given file entry."""
    result: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line.startswith(f"- {file_prefix}"):
            for j in range(i + 1, min(i + 5, len(lines))):
                stripped = lines[j].strip()
                if stripped.startswith("See also:"):
                    result["see_also"] = lines[j]
                elif stripped.startswith("References:"):
                    result["references"] = lines[j]
                elif stripped.startswith("- "):
                    break  # next file entry
            break
    return result


class TestStemFalsePositives:
    """Bug #190: short stem substring matching inflates xref density."""

    def test_config_references_should_not_include_api_via_api_key(self) -> None:
        """config.md has 'api_key' but stem 'api' should NOT match it."""
        tree = _make_tree_with_short_stems()
        result = XrefDenseVariant().render(tree)
        lines = result.splitlines()

        config_sub = _get_sub_lines(lines, "docs/config.md")
        refs = config_sub.get("references", "")

        assert "docs/api.md" not in refs, (
            "Stem 'api' falsely matched 'api_key' in config.md "
            "(bug #190: substring matching without word boundaries)"
        )

    def test_config_references_should_not_include_auth_via_authentication(self) -> None:
        """config.md has 'authentication' but stem 'auth' should NOT match it."""
        tree = _make_tree_with_short_stems()
        result = XrefDenseVariant().render(tree)
        lines = result.splitlines()

        config_sub = _get_sub_lines(lines, "docs/config.md")
        refs = config_sub.get("references", "")

        assert "docs/auth.md" not in refs, (
            "Stem 'auth' falsely matched 'authentication' in config.md "
            "(bug #190: substring matching without word boundaries)"
        )

    def test_auth_references_should_include_api_as_standalone_word(self) -> None:
        """auth.md has 'the api to get' — stem 'api' IS a standalone word."""
        tree = _make_tree_with_short_stems()
        result = XrefDenseVariant().render(tree)
        lines = result.splitlines()

        auth_sub = _get_sub_lines(lines, "docs/auth.md")

        assert "references" in auth_sub, (
            "auth.md should have References (mentions 'api' as standalone word)"
        )
        assert "docs/api.md" in auth_sub["references"]

    def test_mentions_of_does_not_include_compound_match(self) -> None:
        """mentions_of['api'] should NOT include config.md (only 'api_key')."""
        tree = _make_tree_with_short_stems()
        result = XrefDenseVariant().render(tree)
        lines = result.splitlines()

        # api.md's See-also includes section peers + content mentioners.
        # Section peers: auth.md and config.md (same section).
        # Content mentioners of "api": auth.md mentions "api" (standalone),
        # but config.md only has "api_key" — should NOT be a content mentioner.
        # Since both are section peers anyway, we can't distinguish in output.
        # Instead verify via the References of config.md being empty.
        config_sub = _get_sub_lines(lines, "docs/config.md")

        # After the fix, config.md should have NO References line at all
        # because neither "api_key" matches stem "api" nor "authentication"
        # matches stem "auth" at word boundaries.
        assert "references" not in config_sub, (
            "config.md should have no References after fixing word-boundary "
            "matching (bug #190)"
        )
