"""Tests for the LLM-as-judge calibration module."""

from __future__ import annotations

import pytest
from agent_evals.judge.calibrator import (
    CalibrationResult,
    GoldExample,
    JudgeScore,
    build_judge_prompt,
    calibrate,
    compute_cohens_kappa,
    compute_kendall_tau,
    compute_mean_absolute_error,
    compute_spearman,
    parse_judge_response,
)

# ===================================================================
# Helpers
# ===================================================================


def _make_gold(
    example_id: str,
    task_type: str = "retrieval",
    human_score: float = 0.8,
) -> GoldExample:
    return GoldExample(
        example_id=example_id,
        task_type=task_type,
        difficulty="medium",
        question="What is X?",
        response="X is ...",
        human_score=human_score,
        human_rationale="Good answer.",
    )


def _make_judge(
    example_id: str,
    score: float = 0.8,
    model: str = "gpt-4o",
) -> JudgeScore:
    return JudgeScore(
        example_id=example_id,
        judge_model=model,
        score=score,
        rationale="Looks correct.",
        raw_response=f"RATIONALE: Looks correct.\nSCORE: {score}",
    )


# ===================================================================
# compute_cohens_kappa
# ===================================================================


class TestComputeCohensKappa:
    """Tests for compute_cohens_kappa."""

    def test_perfect_agreement(self) -> None:
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = compute_cohens_kappa(scores, scores)
        assert result == pytest.approx(1.0)

    def test_near_random_agreement(self) -> None:
        # Deliberately uncorrelated scores
        a = [0.0, 0.2, 0.4, 0.6, 0.8, 0.1, 0.3, 0.5, 0.7, 0.9]
        b = [0.9, 0.7, 0.5, 0.3, 0.1, 0.8, 0.6, 0.4, 0.2, 0.0]
        result = compute_cohens_kappa(a, b)
        # Reversed scores should have negative or near-zero kappa
        assert result < 0.3

    def test_substantial_agreement(self) -> None:
        # Scores that are close but not identical
        a = [0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4, 0.6, 0.8, 0.95]
        b = [0.15, 0.25, 0.55, 0.65, 0.85, 0.25, 0.45, 0.55, 0.75, 0.9]
        result = compute_cohens_kappa(a, b)
        assert 0.5 <= result <= 1.0

    def test_empty_lists(self) -> None:
        result = compute_cohens_kappa([], [])
        assert result == 0.0

    def test_single_value_lists(self) -> None:
        result = compute_cohens_kappa([0.5], [0.5])
        assert result == 0.0

    def test_identical_constant_scores(self) -> None:
        # All same value in both lists
        a = [0.5, 0.5, 0.5, 0.5]
        b = [0.5, 0.5, 0.5, 0.5]
        result = compute_cohens_kappa(a, b)
        assert result == 1.0

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            compute_cohens_kappa([0.1, 0.2], [0.1])

    def test_boundary_scores(self) -> None:
        # Scores exactly at 0.0 and 1.0
        a = [0.0, 1.0, 0.0, 1.0]
        b = [0.0, 1.0, 0.0, 1.0]
        result = compute_cohens_kappa(a, b)
        assert result == pytest.approx(1.0)


# ===================================================================
# compute_spearman
# ===================================================================


class TestComputeSpearman:
    """Tests for compute_spearman."""

    def test_perfect_positive_correlation(self) -> None:
        a = [0.1, 0.2, 0.3, 0.4, 0.5]
        b = [0.2, 0.4, 0.6, 0.8, 1.0]
        result = compute_spearman(a, b)
        assert result == pytest.approx(1.0)

    def test_perfect_negative_correlation(self) -> None:
        a = [0.1, 0.2, 0.3, 0.4, 0.5]
        b = [1.0, 0.8, 0.6, 0.4, 0.2]
        result = compute_spearman(a, b)
        assert result == pytest.approx(-1.0)

    def test_no_correlation(self) -> None:
        # Scores with no clear monotonic relationship (rho ≈ -0.02)
        a = [0.1, 0.5, 0.3, 0.9, 0.7, 0.2, 0.8, 0.4, 0.6, 0.0]
        b = [0.3, 0.7, 0.1, 0.5, 0.9, 0.4, 0.0, 0.8, 0.2, 0.6]
        result = compute_spearman(a, b)
        assert -0.5 < result < 0.5

    def test_identical_values(self) -> None:
        a = [0.5, 0.5, 0.5, 0.5]
        b = [0.1, 0.2, 0.3, 0.4]
        result = compute_spearman(a, b)
        assert result == 0.0

    def test_empty_lists(self) -> None:
        result = compute_spearman([], [])
        assert result == 0.0

    def test_single_value(self) -> None:
        result = compute_spearman([0.5], [0.5])
        assert result == 0.0

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            compute_spearman([0.1, 0.2], [0.1])


# ===================================================================
# compute_kendall_tau
# ===================================================================


class TestComputeKendallTau:
    """Tests for compute_kendall_tau."""

    def test_perfect_agreement(self) -> None:
        a = [0.1, 0.2, 0.3, 0.4, 0.5]
        b = [0.2, 0.4, 0.6, 0.8, 1.0]
        result = compute_kendall_tau(a, b)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_reversed(self) -> None:
        a = [0.1, 0.2, 0.3, 0.4, 0.5]
        b = [1.0, 0.8, 0.6, 0.4, 0.2]
        result = compute_kendall_tau(a, b)
        assert result == pytest.approx(-1.0, abs=0.01)

    def test_handle_ties(self) -> None:
        a = [0.1, 0.1, 0.3, 0.3, 0.5]
        b = [0.2, 0.2, 0.6, 0.6, 1.0]
        result = compute_kendall_tau(a, b)
        # With ties, tau should still be positive for concordant pairs
        assert result > 0.0

    def test_empty_lists(self) -> None:
        result = compute_kendall_tau([], [])
        assert result == 0.0

    def test_single_value(self) -> None:
        result = compute_kendall_tau([0.5], [0.5])
        assert result == 0.0

    def test_constant_values(self) -> None:
        a = [0.5, 0.5, 0.5]
        b = [0.1, 0.2, 0.3]
        result = compute_kendall_tau(a, b)
        assert result == 0.0

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            compute_kendall_tau([0.1], [0.1, 0.2])


# ===================================================================
# compute_mean_absolute_error
# ===================================================================


class TestComputeMeanAbsoluteError:
    """Tests for compute_mean_absolute_error."""

    def test_perfect_match(self) -> None:
        a = [0.1, 0.5, 0.9]
        result = compute_mean_absolute_error(a, a)
        assert result == pytest.approx(0.0)

    def test_known_differences(self) -> None:
        predicted = [0.0, 0.5, 1.0]
        actual = [0.1, 0.5, 0.8]
        # |0.0-0.1| + |0.5-0.5| + |1.0-0.8| = 0.1 + 0.0 + 0.2 = 0.3 / 3 = 0.1
        result = compute_mean_absolute_error(predicted, actual)
        assert result == pytest.approx(0.1)

    def test_empty_lists(self) -> None:
        result = compute_mean_absolute_error([], [])
        assert result == 0.0

    def test_single_element(self) -> None:
        result = compute_mean_absolute_error([0.3], [0.7])
        assert result == pytest.approx(0.4)

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            compute_mean_absolute_error([0.1, 0.2], [0.1])


# ===================================================================
# build_judge_prompt
# ===================================================================


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt."""

    def test_returns_list_of_message_dicts(self) -> None:
        messages = build_judge_prompt(
            task_type="retrieval",
            question="What is X?",
            response="X is Y.",
        )
        assert isinstance(messages, list)
        assert len(messages) == 2
        for msg in messages:
            assert "role" in msg
            assert "content" in msg

    def test_system_message_contains_rubric(self) -> None:
        messages = build_judge_prompt(
            task_type="retrieval",
            question="What is X?",
            response="X is Y.",
        )
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "retrieval" in system_msg["content"].lower()
        assert "SCORE" in system_msg["content"]
        assert "RATIONALE" in system_msg["content"]

    def test_user_message_contains_question_and_response(self) -> None:
        messages = build_judge_prompt(
            task_type="retrieval",
            question="What is X?",
            response="X is Y.",
        )
        user_msg = messages[1]
        assert user_msg["role"] == "user"
        assert "What is X?" in user_msg["content"]
        assert "X is Y." in user_msg["content"]

    def test_different_task_types_produce_different_rubrics(self) -> None:
        retrieval_msgs = build_judge_prompt(
            task_type="retrieval",
            question="Q",
            response="R",
        )
        code_msgs = build_judge_prompt(
            task_type="code_generation",
            question="Q",
            response="R",
        )
        assert retrieval_msgs[0]["content"] != code_msgs[0]["content"]

    def test_custom_rubric_overrides_default(self) -> None:
        custom = "My custom rubric for this evaluation."
        messages = build_judge_prompt(
            task_type="retrieval",
            question="Q",
            response="R",
            rubric=custom,
        )
        assert custom in messages[0]["content"]

    def test_unknown_task_type_uses_generic_rubric(self) -> None:
        messages = build_judge_prompt(
            task_type="unknown_type",
            question="Q",
            response="R",
        )
        assert "correctness" in messages[0]["content"].lower()

    def test_all_known_task_types_have_rubrics(self) -> None:
        known_types = [
            "retrieval",
            "fact_extraction",
            "code_generation",
            "agentic",
            "multi_hop",
            "negative",
            "compositional",
            "robustness",
            "disambiguation",
            "conflicting",
            "efficiency",
        ]
        for task_type in known_types:
            messages = build_judge_prompt(
                task_type=task_type,
                question="Q",
                response="R",
            )
            # Each known type should produce a system message mentioning the type
            assert task_type in messages[0]["content"].lower()

    def test_system_message_instructs_chain_of_thought(self) -> None:
        messages = build_judge_prompt(
            task_type="retrieval",
            question="Q",
            response="R",
        )
        system_content = messages[0]["content"]
        assert "step-by-step" in system_content.lower() or "reasoning" in system_content.lower()

    def test_system_message_penalizes_verbosity(self) -> None:
        messages = build_judge_prompt(
            task_type="retrieval",
            question="Q",
            response="R",
        )
        system_content = messages[0]["content"].lower()
        assert "verbose" in system_content


# ===================================================================
# parse_judge_response
# ===================================================================


class TestParseJudgeResponse:
    """Tests for parse_judge_response."""

    def test_valid_format(self) -> None:
        response = "RATIONALE: The answer is correct and complete.\nSCORE: 0.85"
        score, rationale = parse_judge_response(response)
        assert score == pytest.approx(0.85)
        assert "correct" in rationale.lower()

    def test_valid_format_with_extra_whitespace(self) -> None:
        response = "RATIONALE:  Some reasoning here. \n  SCORE:   0.7  "
        score, rationale = parse_judge_response(response)
        assert score == pytest.approx(0.7)
        assert "reasoning" in rationale.lower()

    def test_case_insensitive_score(self) -> None:
        response = "RATIONALE: Good.\nScore: 0.8"
        score, rationale = parse_judge_response(response)
        assert score == pytest.approx(0.8)

    def test_score_zero(self) -> None:
        response = "RATIONALE: Completely wrong.\nSCORE: 0.0"
        score, _ = parse_judge_response(response)
        assert score == pytest.approx(0.0)

    def test_score_one(self) -> None:
        response = "RATIONALE: Perfect.\nSCORE: 1.0"
        score, _ = parse_judge_response(response)
        assert score == pytest.approx(1.0)

    def test_integer_score(self) -> None:
        response = "RATIONALE: Okay.\nSCORE: 1"
        score, _ = parse_judge_response(response)
        assert score == pytest.approx(1.0)

    def test_missing_score_raises(self) -> None:
        response = "RATIONALE: The answer is correct."
        with pytest.raises(ValueError, match="Could not parse SCORE"):
            parse_judge_response(response)

    def test_score_above_range_raises(self) -> None:
        response = "RATIONALE: Great.\nSCORE: 1.5"
        with pytest.raises(ValueError, match="out of range"):
            parse_judge_response(response)

    def test_score_below_range_raises(self) -> None:
        response = "RATIONALE: Bad.\nSCORE: -0.1"
        with pytest.raises(ValueError, match="Could not parse SCORE"):
            parse_judge_response(response)

    def test_multiline_rationale(self) -> None:
        response = (
            "RATIONALE: First the answer addresses the question.\n"
            "Then it provides supporting evidence.\n"
            "Overall it is thorough.\n"
            "SCORE: 0.9"
        )
        score, rationale = parse_judge_response(response)
        assert score == pytest.approx(0.9)
        assert "evidence" in rationale.lower()

    def test_empty_response_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse SCORE"):
            parse_judge_response("")

    def test_score_with_extra_text_after(self) -> None:
        response = "RATIONALE: Good answer.\nSCORE: 0.75\nSome trailing text."
        score, rationale = parse_judge_response(response)
        assert score == pytest.approx(0.75)


# ===================================================================
# calibrate
# ===================================================================


class TestCalibrate:
    """Tests for calibrate."""

    def test_perfect_agreement_passes(self) -> None:
        golds = [
            _make_gold(f"ex_{i}", "retrieval", score)
            for i, score in enumerate([0.1, 0.3, 0.5, 0.7, 0.9])
        ]
        judges = [
            _make_judge(f"ex_{i}", score)
            for i, score in enumerate([0.1, 0.3, 0.5, 0.7, 0.9])
        ]
        result = calibrate(golds, judges)
        assert result.passed is True
        assert result.cohens_kappa == pytest.approx(1.0)
        assert result.spearman_rho == pytest.approx(1.0)
        assert result.kendalls_tau == pytest.approx(1.0, abs=0.01)
        assert result.mean_absolute_error == pytest.approx(0.0)
        assert result.total_examples == 5

    def test_poor_agreement_fails(self) -> None:
        golds = [
            _make_gold(f"ex_{i}", "retrieval", score)
            for i, score in enumerate([0.1, 0.3, 0.5, 0.7, 0.9])
        ]
        # Reversed scores -> poor agreement
        judges = [
            _make_judge(f"ex_{i}", score)
            for i, score in enumerate([0.9, 0.7, 0.5, 0.3, 0.1])
        ]
        result = calibrate(golds, judges)
        assert result.passed is False

    def test_per_type_breakdown(self) -> None:
        golds = [
            _make_gold("r_0", "retrieval", 0.1),
            _make_gold("r_1", "retrieval", 0.5),
            _make_gold("r_2", "retrieval", 0.9),
            _make_gold("c_0", "code_generation", 0.2),
            _make_gold("c_1", "code_generation", 0.6),
            _make_gold("c_2", "code_generation", 0.95),
        ]
        judges = [
            _make_judge("r_0", 0.1),
            _make_judge("r_1", 0.5),
            _make_judge("r_2", 0.9),
            _make_judge("c_0", 0.2),
            _make_judge("c_1", 0.6),
            _make_judge("c_2", 0.95),
        ]
        result = calibrate(golds, judges)
        assert "retrieval" in result.per_type_kappa
        assert "code_generation" in result.per_type_kappa
        assert "retrieval" in result.per_type_spearman
        assert "code_generation" in result.per_type_spearman

    def test_mixed_types_one_failing(self) -> None:
        # Retrieval: perfect agreement
        golds = [
            _make_gold("r_0", "retrieval", 0.1),
            _make_gold("r_1", "retrieval", 0.5),
            _make_gold("r_2", "retrieval", 0.9),
        ]
        judges_good = [
            _make_judge("r_0", 0.1),
            _make_judge("r_1", 0.5),
            _make_judge("r_2", 0.9),
        ]
        # Code generation: poor agreement (reversed)
        golds += [
            _make_gold("c_0", "code_generation", 0.1),
            _make_gold("c_1", "code_generation", 0.5),
            _make_gold("c_2", "code_generation", 0.9),
        ]
        judges_bad = [
            _make_judge("c_0", 0.9),
            _make_judge("c_1", 0.5),
            _make_judge("c_2", 0.1),
        ]
        result = calibrate(golds, judges_good + judges_bad)
        assert "code_generation" in result.flagged_types

    def test_empty_gold_examples(self) -> None:
        judges = [_make_judge("ex_0", 0.5)]
        result = calibrate([], judges)
        assert result.total_examples == 0
        assert result.passed is False

    def test_empty_judge_scores(self) -> None:
        golds = [_make_gold("ex_0", "retrieval", 0.5)]
        result = calibrate(golds, [])
        assert result.total_examples == 0
        assert result.passed is False

    def test_no_overlapping_ids(self) -> None:
        golds = [_make_gold("gold_0", "retrieval", 0.5)]
        judges = [_make_judge("judge_0", 0.5)]
        result = calibrate(golds, judges)
        assert result.total_examples == 0
        assert result.passed is False

    def test_judge_model_propagated(self) -> None:
        golds = [_make_gold("ex_0", "retrieval", 0.5)]
        judges = [_make_judge("ex_0", 0.5, model="claude-3-opus")]
        result = calibrate(golds, judges)
        assert result.judge_model == "claude-3-opus"

    def test_result_is_calibration_result(self) -> None:
        golds = [
            _make_gold(f"ex_{i}", "retrieval", s)
            for i, s in enumerate([0.1, 0.5, 0.9])
        ]
        judges = [
            _make_judge(f"ex_{i}", s) for i, s in enumerate([0.1, 0.5, 0.9])
        ]
        result = calibrate(golds, judges)
        assert isinstance(result, CalibrationResult)

    def test_custom_thresholds(self) -> None:
        # With very lenient thresholds, even moderate agreement passes
        golds = [
            _make_gold(f"ex_{i}", "retrieval", score)
            for i, score in enumerate([0.1, 0.3, 0.5, 0.7, 0.9])
        ]
        judges = [
            _make_judge(f"ex_{i}", score)
            for i, score in enumerate([0.15, 0.35, 0.45, 0.75, 0.85])
        ]
        result = calibrate(
            golds, judges, kappa_threshold=0.3, spearman_threshold=0.5
        )
        assert result.passed is True

    def test_mae_reflects_differences(self) -> None:
        golds = [
            _make_gold("ex_0", "retrieval", 0.0),
            _make_gold("ex_1", "retrieval", 0.5),
            _make_gold("ex_2", "retrieval", 1.0),
        ]
        judges = [
            _make_judge("ex_0", 0.1),
            _make_judge("ex_1", 0.5),
            _make_judge("ex_2", 0.8),
        ]
        result = calibrate(golds, judges)
        # MAE = (0.1 + 0.0 + 0.2) / 3 = 0.1
        assert result.mean_absolute_error == pytest.approx(0.1)
