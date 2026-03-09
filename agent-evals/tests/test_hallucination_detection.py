"""Tests for hallucination detection via LLM-as-judge."""

from __future__ import annotations

import json

import pytest

from agent_evals.judge.hallucination import (
    HallucinationResult,
    build_hallucination_prompt,
    build_hallucination_rubric,
    parse_hallucination_result,
)


class TestHallucinationRubric:
    """Tests for build_hallucination_rubric."""

    def test_build_rubric_returns_dict(self) -> None:
        rubric = build_hallucination_rubric()
        assert isinstance(rubric, dict)
        assert "system" in rubric
        assert "criteria" in rubric

    def test_rubric_mentions_grounding(self) -> None:
        rubric = build_hallucination_rubric()
        assert "grounded" in rubric["criteria"]


class TestHallucinationPrompt:
    """Tests for build_hallucination_prompt."""

    def test_build_prompt_includes_source_docs(self) -> None:
        prompt = build_hallucination_prompt(
            response="Some answer",
            source_docs="Source material here",
            question="What is X?",
        )
        user_msg = prompt[-1]["content"]
        assert "Source material here" in user_msg

    def test_build_prompt_includes_response(self) -> None:
        prompt = build_hallucination_prompt(
            response="The answer is 42",
            source_docs="Docs",
            question="What?",
        )
        user_msg = prompt[-1]["content"]
        assert "The answer is 42" in user_msg


class TestParseHallucinationResult:
    """Tests for parse_hallucination_result."""

    def test_parse_grounded(self) -> None:
        raw = json.dumps(
            {
                "hallucination_score": 0.0,
                "type": "grounded",
                "flagged_claims": [],
            }
        )
        result = parse_hallucination_result(raw)
        assert result.score == 0.0
        assert result.hallucination_type == "grounded"
        assert result.flagged_claims == []

    def test_parse_fabrication(self) -> None:
        raw = json.dumps(
            {
                "hallucination_score": 0.8,
                "type": "fabrication",
                "flagged_claims": ["claim A", "claim B"],
            }
        )
        result = parse_hallucination_result(raw)
        assert result.score == 0.8
        assert result.hallucination_type == "fabrication"
        assert result.flagged_claims == ["claim A", "claim B"]

    def test_parse_contradiction(self) -> None:
        raw = json.dumps(
            {
                "hallucination_score": 1.0,
                "type": "contradiction",
                "flagged_claims": ["contradicted fact"],
            }
        )
        result = parse_hallucination_result(raw)
        assert result.score == 1.0
        assert result.hallucination_type == "contradiction"

    def test_parse_malformed_returns_default(self) -> None:
        result = parse_hallucination_result("not valid json at all")
        assert result.score == 0.5
        assert result.hallucination_type == "unknown"
        assert result.flagged_claims == []


class TestHallucinationResult:
    """Tests for HallucinationResult dataclass."""

    def test_to_dict(self) -> None:
        result = HallucinationResult(
            score=0.3,
            hallucination_type="extrapolation",
            flagged_claims=["inferred claim"],
        )
        d = result.to_dict()
        assert d == {
            "hallucination_score": 0.3,
            "hallucination_type": "extrapolation",
            "flagged_claims": ["inferred claim"],
        }
