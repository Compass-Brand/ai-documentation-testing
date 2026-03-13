"""Phase C integration tests -- verify all components work together."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from agent_index.models import DocFile, DocTree
from conftest import make_mock_task


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Auth\nUse OAuth2 for authentication.",
                size_bytes=35, token_count=8, tier="required",
                section="Guides", summary="OAuth2 auth guide",
                related=["api/users.md"],
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nGET /users returns a list of users.",
                size_bytes=48, token_count=12, tier="recommended",
                section="API", summary="Users endpoint reference",
                related=[],
            ),
        },
        scanned_at=datetime(2026, 1, 1), source="/test", total_tokens=20,
    )


class TestMCPNativeEndToEnd:
    def test_full_flow(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy(max_turns=5)
        doc_tree = _make_doc_tree()
        strategy.setup("index content", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index content", task, doc_tree)
        client = MagicMock()
        gen = MagicMock()
        gen.content = "OAuth2 is used for authentication."
        gen.tool_calls = None
        gen.prompt_tokens = 50
        gen.completion_tokens = 10
        gen.total_tokens = 60
        gen.cost = 0.002
        client.complete.return_value = gen
        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert "OAuth2" in result.final_response
        assert result.strategy_metadata["resource_count"] == 2
        strategy.teardown()


class TestCompressionEndToEnd:
    def test_full_flow(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="algorithmic")
        doc_tree = _make_doc_tree()
        rendered = "# Documentation\n\nThis is the full rendered index."
        strategy.setup(rendered, doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare(rendered, task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "algorithmic"
        assert prepared.strategy_metadata["compression_ratio"] <= 1.0


class TestNewAxesDiscovery:
    def test_axis_11_discovered(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        variants = get_variants_for_axis(11)
        assert len(variants) >= 8

    def test_axis_12_discovered(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        variants = get_variants_for_axis(12)
        assert len(variants) >= 9


class TestHallucinationDetection:
    def test_full_detection_flow(self):
        from agent_evals.judge.hallucination import (
            build_hallucination_prompt,
            parse_hallucination_result,
        )
        messages = build_hallucination_prompt(
            response="OAuth2 tokens expire in 1 hour.",
            source_docs="# Auth\nOAuth2 tokens expire after 1 hour.",
            question="How long do tokens last?",
        )
        assert len(messages) == 2
        result = parse_hallucination_result('{"hallucination_score": 0.0, "type": "grounded", "flagged_claims": []}')
        assert result.score == 0.0
        assert result.hallucination_type == "grounded"


class TestModifiers:
    def test_compaction_modifier_wraps_strategy(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier
        inner = MagicMock()
        inner.name.return_value = "full_context"
        modifier = CompactionModifier(inner, compaction_ratio=0.5)
        assert "compaction" in modifier.name()

    def test_dynamic_tools_modifier_wraps_strategy(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier
        inner = MagicMock()
        inner.name.return_value = "tool_based"
        modifier = DynamicToolModifier(inner, mode="restricted")
        assert "restricted" in modifier.name()


class TestCacheAnalysis:
    def test_report_with_variant_data(self):
        from agent_evals.reports.cache_analysis import build_cache_report
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml", "cache_write_tokens": 200},
            {"cached_tokens": 600, "prompt_tokens": 1000, "variant_name": "yaml", "cache_write_tokens": 400},
            {"cached_tokens": 100, "prompt_tokens": 1000, "variant_name": "random", "cache_write_tokens": 900},
        ]
        report = build_cache_report(trials)
        assert report["yaml"]["mean_hit_rate"] == pytest.approx(0.7)
        assert report["random"]["mean_hit_rate"] == pytest.approx(0.1)
