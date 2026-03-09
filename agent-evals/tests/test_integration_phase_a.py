"""Phase A integration tests — dataset -> strategy -> judge -> report."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.datasets import list_available, load_all as load_all_datasets
from agent_evals.datasets.source import load_from_source
from agent_evals.judge.calibrator import build_judge_prompt, parse_judge_response
from agent_evals.reports.recommendations import (
    Finding,
    extract_strategy_breakdowns,
    generate_findings,
    render_findings_text,
)
from agent_evals.reports.statistics import kendalls_w
from agent_evals.runner import EvalRunConfig


class TestDatasetRegistryIntegration:
    def test_all_9_adapters_register(self):
        load_all_datasets()
        available = list_available()
        assert len(available) >= 9
        names = {a["name"] for a in available}
        expected = {
            "repliqa", "ibm-techqa", "code-rag-bench", "ds1000",
            "swe-bench", "multihop-rag", "ambigqa", "bigcodebench",
            "wikicontradict",
        }
        assert expected.issubset(names), f"Missing: {expected - names}"


class TestSourceRoutingIntegration:
    def test_gold_standard_returns_none(self):
        result = load_from_source("gold_standard")
        assert result is None

    def test_unknown_source_raises(self):
        with pytest.raises(KeyError):
            load_from_source("nonexistent_dataset_xyz")


class TestJudgePromptIntegration:
    def test_judge_prompt_for_all_task_types(self):
        """Judge can build prompts for every core task type."""
        task_types = [
            "retrieval", "fact_extraction", "code_generation", "agentic",
            "multi_hop", "negative", "compositional", "robustness",
            "disambiguation", "conflicting", "efficiency",
        ]
        for task_type in task_types:
            messages = build_judge_prompt(task_type, "Test question", "Test response")
            assert len(messages) == 2
            assert messages[0]["role"] == "system"

    def test_parse_judge_response_roundtrip(self):
        """A well-formed judge response parses correctly."""
        response = "RATIONALE: The answer is accurate and complete.\nSCORE: 0.85"
        score, rationale = parse_judge_response(response)
        assert score == 0.85
        assert "accurate" in rationale


class TestRecommendationsIntegration:
    def test_generate_and_render_findings(self):
        """Full pipeline: ANOVA results -> findings -> text output."""
        anova = {
            "axis_1_structure": {"p_value": 0.001, "significant": True},
            "axis_5_scale": {"p_value": 0.03, "significant": True},
            "axis_7_noise": {"p_value": 0.8, "significant": False},
        }
        effects = {
            "axis_1_structure": {"flat": 65.0, "2-tier": 82.0, "3-tier": 78.0},
            "axis_5_scale": {"5pct": 55.0, "50pct": 78.0, "100pct": 80.0},
            "axis_7_noise": {"clean": 76.0, "25pct": 74.0},
        }
        findings = generate_findings(anova, effects)
        assert len(findings) == 2

        text = render_findings_text(findings)
        assert "2-tier" in text
        assert "Documentation hierarchy" in text
        assert "noise" not in text.lower()


class TestJudgeConfigIntegration:
    def test_judge_config_fields_on_eval_run_config(self):
        """EvalRunConfig has all Phase A judge config fields."""
        config = EvalRunConfig(
            judge_enabled=True,
            judge_mode="poll",
            judge_sample_rate=10,
            judge_model="openrouter/openai/gpt-5-mini",
            poll_models=["model_a", "model_b", "model_c"],
        )
        assert config.judge_enabled is True
        assert config.judge_mode == "poll"
        assert config.judge_sample_rate == 10
        assert len(config.poll_models) == 3


class TestDatasetSourceTaguchiEndToEnd:
    def test_dataset_source_end_to_end(self):
        """End-to-end: adapter loads -> DocTree built -> recommendations generated."""
        mock_rows = [
            {
                "question": f"Q{i}?",
                "answer": "unanswerable" if i % 2 == 0 else f"Answer {i}",
                "document_id": f"doc_{i:03d}",
                "document_extracted": f"# Document {i}\nContent for document {i}.",
                "document_topic": "general",
                "document_path": f"docs/doc_{i:03d}.md",
                "category": "unanswerable" if i % 2 == 0 else "answerable",
            }
            for i in range(20)
        ]

        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_rows,
        ), patch(
            "agent_evals.datasets.source.DatasetCache",
        ) as mock_cache_cls:
            mock_cache = mock_cache_cls.return_value
            mock_cache.is_prepared.return_value = False
            mock_cache.task_dir.return_value = Path(tempfile.mkdtemp())
            mock_cache.doc_tree_path.return_value = Path("/tmp/fake/tree.json")

            result = load_from_source("repliqa", limit=20)
            assert result is not None
            tasks, doc_tree, source_name = result
            assert source_name == "repliqa"
            assert len(doc_tree.files) > 0

        # Verify recommendations pipeline with synthetic ANOVA results
        anova = {"axis_1_structure": {"p_value": 0.01, "significant": True}}
        effects = {"axis_1_structure": {"flat": 62.0, "2-tier": 79.0}}
        findings = generate_findings(anova, effects)
        assert len(findings) == 1

        text = render_findings_text(findings)
        assert "2-tier" in text


class TestFullPhaseAExitCriteria:
    def test_exit_criterion_1_adapters_registered(self):
        """At least 9 dataset adapters register."""
        load_all_datasets()
        available = list_available()
        assert len(available) >= 9

    def test_exit_criterion_2_strategies_exist(self):
        """All 4 context strategies can be instantiated."""
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        for name in ["full_context", "system_prompt", "rag", "tool_based"]:
            strategy = get_strategy_by_name(name)
            assert strategy is not None, f"Strategy '{name}' not found"

    def test_exit_criterion_3_anova_identifies_significant_factors(self):
        """ANOVA can identify significant factors from main effects."""
        anova = {
            "axis_1_structure": {"p_value": 0.003, "significant": True},
            "axis_2_metadata": {"p_value": 0.42, "significant": False},
        }
        effects = {
            "axis_1_structure": {"flat": 60.0, "2-tier": 80.0, "3-tier": 72.0},
        }
        findings = generate_findings(anova, effects)
        assert len(findings) >= 1
        assert findings[0].factor_name == "axis_1_structure"

    def test_exit_criterion_4_per_strategy_breakdowns(self):
        """Recommendations include per-strategy breakdowns."""
        strategy_phase_results = {
            "full_context": {
                "main_effects": {
                    "axis_1": {"flat": 58.0, "2-tier": 82.0, "3-tier": 74.0},
                },
            },
            "system_prompt": {
                "main_effects": {
                    "axis_1": {"flat": 55.0, "2-tier": 79.0, "3-tier": 76.0},
                },
            },
            "rag": {
                "main_effects": {
                    "axis_1": {"flat": 52.0, "2-tier": 71.0, "3-tier": 80.0},
                },
            },
            "tool_based": {
                "main_effects": {
                    "axis_1": {"flat": 60.0, "2-tier": 83.0, "3-tier": 77.0},
                },
            },
        }
        breakdowns = extract_strategy_breakdowns(
            strategy_phase_results, factor="axis_1"
        )
        assert len(breakdowns) == 4
        for bd in breakdowns:
            assert bd.best_level in ("flat", "2-tier", "3-tier")
            assert bd.effect_size > 0

    def test_exit_criterion_5_cross_strategy_concordance(self):
        """Kendall's W measures cross-strategy agreement."""
        strategy_effects = {
            "full_context": {"flat": 58.0, "2-tier": 82.0, "3-tier": 74.0},
            "system_prompt": {"flat": 55.0, "2-tier": 79.0, "3-tier": 76.0},
            "rag": {"flat": 52.0, "2-tier": 71.0, "3-tier": 80.0},
            "tool_based": {"flat": 60.0, "2-tier": 83.0, "3-tier": 77.0},
        }

        levels = ["flat", "2-tier", "3-tier"]
        rankings = []
        for effects in strategy_effects.values():
            sorted_levels = sorted(levels, key=lambda lv: effects[lv])
            ranks = [sorted_levels.index(lv) + 1 for lv in levels]
            rankings.append(ranks)

        w = kendalls_w(rankings)
        assert 0.0 <= w <= 1.0
        assert w > 0.5  # Moderate-to-high concordance
