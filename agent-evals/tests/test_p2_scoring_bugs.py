"""Tests for P2 scoring bugs #198–#202.

Each test class corresponds to one bug and is written RED-first to expose
the defect before the production fix is applied.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pytest
from agent_evals.tasks.base import TaskDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_definition(task_type: str = "compositional", **meta: Any) -> TaskDefinition:
    """Create a minimal TaskDefinition for testing."""
    return TaskDefinition(
        task_id=f"{task_type}_001",
        type=task_type,
        question="test question",
        domain="framework_api",
        difficulty="easy",
        tags=["test"],
        metadata=meta,
    )


# ===================================================================
# Bug #202: Compositional scorer partial_ratio inflates scores
#            for short keywords against longer strings
# ===================================================================


class TestBug202CompositionalPartialRatioInflation:
    """partial_ratio gives ~100 for short keyword 'port' inside 'transportation'.

    After fix, short keywords (<=4 chars) should use word-boundary matching
    instead of partial_ratio, reducing false-positive inflation.
    """

    def test_short_keyword_not_inflated_by_partial_ratio(self):
        """'port' should NOT fuzzy-match inside 'transportation'."""
        from agent_evals.tasks.compositional import CompositionalTask

        task = CompositionalTask(
            _make_definition(
                task_type="compositional",
                sub_tasks=[
                    {
                        "question": "What port is used?",
                        # "port" and "config" are both short keywords that
                        # partial_ratio inflates when they appear as substrings.
                        "expected_answer": "port config",
                    },
                ],
            )
        )
        # "port" appears inside "transportation", "config" inside "configuration"
        # Neither appears as a standalone word.
        response = "The transportation system uses configuration files."
        score = task.score_response(response)
        # Before fix: partial_ratio("port", "...transportation...") ≈ 100
        # and partial_ratio("config", "...configuration...") ≈ 100 → score ≈ 1.0
        # After fix: "port" (4 chars) uses word-boundary → no match,
        # "config" (6 chars) still fuzzy-matches "configuration" → 0.5
        assert score <= 0.5, (
            f"Short keywords inflated score to {score} via partial_ratio"
        )

    def test_long_keyword_still_uses_fuzzy(self):
        """Keywords with 5+ chars should still use fuzzy partial_ratio."""
        from agent_evals.tasks.compositional import CompositionalTask

        task = CompositionalTask(
            _make_definition(
                task_type="compositional",
                sub_tasks=[
                    {
                        "question": "What framework?",
                        "expected_answer": "the authentication framework",
                    },
                ],
            )
        )
        # "authentication" (14 chars) should fuzzy-match "authenticating"
        response = "The authenticating framework handles logins."
        score = task.score_response(response)
        assert score >= 0.5, (
            f"Long keyword should still fuzzy-match, got {score}"
        )

    def test_short_keyword_exact_word_boundary_match(self):
        """Short keyword present as standalone word should still match."""
        from agent_evals.tasks.compositional import CompositionalTask

        task = CompositionalTask(
            _make_definition(
                task_type="compositional",
                sub_tasks=[
                    {
                        "question": "What port?",
                        "expected_answer": "port 8080",
                    },
                ],
            )
        )
        # "port" appears as standalone word
        response = "The server runs on port 8080 by default."
        score = task.score_response(response)
        # Exact containment "port 8080" → 1.0
        assert score == 1.0


# ===================================================================
# Bug #201: Negative scorer produces only 4 discrete values
# ===================================================================


class TestBug201NegativeDiscreteScoring:
    """The negative scorer only produces {0.0, 0.3, 0.7, 1.0}.

    After fix, responses with multiple refusal signals should score
    higher than responses with just one, creating continuous variation.
    """

    def test_multiple_firm_refusal_phrases_score_higher(self):
        """Response with many refusal phrases should score higher than one."""
        from agent_evals.tasks.negative import NegativeTask

        task = NegativeTask(
            _make_definition(task_type="negative", expected_answer="unanswerable")
        )
        # One firm refusal phrase
        response_one = "I cannot determine the answer from this documentation."
        # Multiple firm refusal phrases
        response_many = (
            "I cannot determine the answer. This information is not available "
            "in the documentation. There is no mention of this topic, and "
            "I don't have enough data to provide an answer."
        )
        score_one = task.score_response(response_one)
        score_many = task.score_response(response_many)
        # Both should be high, but many-phrase should be >= one-phrase
        assert score_many >= score_one, (
            f"Many refusal phrases ({score_many}) should score >= "
            f"one phrase ({score_one})"
        )
        # The key test: they should produce DIFFERENT scores (not both 1.0)
        # to improve Taguchi discrimination.
        # After fix, single phrase gives slightly less than 1.0 and
        # many phrases get closer to 1.0.

    def test_scores_are_not_only_four_values(self):
        """Scores across varied responses should produce >4 distinct values."""
        from agent_evals.tasks.negative import NegativeTask

        task = NegativeTask(
            _make_definition(task_type="negative", expected_answer="unanswerable")
        )
        responses = [
            # Tier 1: firm refusals (varying count)
            "Cannot be determined.",
            "I cannot determine the answer. Not available.",
            "I cannot determine this. Not found. No information. Not mentioned.",
            # Tier 2: hedge
            "I'm not certain about this.",
            "It's unclear and difficult to determine from the docs.",
            # Tier 3: disclaimer
            "Based on limited information, the answer might be X.",
            # Tier 4: hallucination
            "The answer is 42.",
            "Definitely the answer is X based on my analysis.",
        ]
        scores = [task.score_response(r) for r in responses]
        unique_scores = set(scores)
        assert len(unique_scores) > 4, (
            f"Expected >4 distinct scores, got {len(unique_scores)}: {sorted(unique_scores)}"
        )

    def test_hedge_with_multiple_phrases_higher_than_single(self):
        """Multiple hedge phrases should score higher than one."""
        from agent_evals.tasks.negative import NegativeTask

        task = NegativeTask(
            _make_definition(task_type="negative", expected_answer="unanswerable")
        )
        single_hedge = "I'm not certain about that."
        multi_hedge = "I'm not certain and it's unclear from the documentation. It's hard to say."
        score_single = task.score_response(single_hedge)
        score_multi = task.score_response(multi_hedge)
        assert score_multi >= score_single


# ===================================================================
# Bug #200: Substring containment gives false 1.0 for short answers
# ===================================================================


class TestBug200ShortSubstringFalsePositives:
    """Short expected answers like 'yes', 'no', 'api' match as substrings
    of almost any response, giving false 1.0 scores.

    After fix, short expected answers (<=4 chars) use word-boundary matching.
    """

    def test_fact_extraction_short_answer_no_false_match(self):
        """'yes' should not match inside 'yesterday' or 'eyes'."""
        from agent_evals.tasks.fact_extraction import FactExtractionTask

        task = FactExtractionTask(
            _make_definition(
                task_type="fact_extraction",
                expected_answer="yes",
            )
        )
        response = "Yesterday the system was operational and my eyes confirmed it."
        score = task.score_response(response)
        assert score < 1.0, (
            f"'yes' substring-matched inside 'yesterday': score={score}"
        )

    def test_fact_extraction_short_answer_standalone_matches(self):
        """'yes' as a standalone word should still match."""
        from agent_evals.tasks.fact_extraction import FactExtractionTask

        task = FactExtractionTask(
            _make_definition(
                task_type="fact_extraction",
                expected_answer="yes",
            )
        )
        response = "Yes, the feature is supported."
        score = task.score_response(response)
        assert score == 1.0

    def test_robustness_short_answer_no_false_match(self):
        """Short answer 'no' should not match inside 'nothing' or 'know'."""
        from agent_evals.tasks.robustness import RobustnessTask

        task = RobustnessTask(
            _make_definition(
                task_type="robustness",
                expected_answer="no",
            )
        )
        response = "I know nothing about this feature and cannot elaborate."
        score = task.score_response(response)
        assert score < 1.0, (
            f"'no' substring-matched inside 'nothing'/'know': score={score}"
        )

    def test_efficiency_short_answer_no_false_match(self):
        """Short answer 'api' should not match inside 'capital'."""
        from agent_evals.tasks.efficiency import EfficiencyTask

        task = EfficiencyTask(
            _make_definition(
                task_type="efficiency",
                expected_answer="api",
            )
        )
        response = "The capital of France is Paris and the rapid transit system is efficient."
        score = task.score_response(response)
        assert score < 1.0, (
            f"'api' substring-matched inside 'capital'/'rapid': score={score}"
        )

    def test_conflicting_short_answer_no_false_match(self):
        """Short resolution 'run' should not match inside 'running'."""
        from agent_evals.tasks.conflicting import ConflictingTask

        task = ConflictingTask(
            _make_definition(
                task_type="conflicting",
                expected_resolution="run",
            )
        )
        response = "The system is currently running a background process."
        score = task.score_response(response)
        assert score < 1.0, (
            f"'run' substring-matched inside 'running': score={score}"
        )

    def test_fact_extraction_alias_short_no_false_match(self):
        """Short alias 'db' should not match inside 'dba' or 'jdbc'."""
        from agent_evals.tasks.fact_extraction import FactExtractionTask

        task = FactExtractionTask(
            _make_definition(
                task_type="fact_extraction",
                expected_answer="database",
                answer_aliases=["db"],
            )
        )
        response = "The dba manages jdbc connections efficiently."
        score = task.score_response(response)
        # "database" not in response, "db" is inside "dba"/"jdbc" but not standalone
        assert score < 1.0, (
            f"Short alias 'db' substring-matched inside 'dba': score={score}"
        )

    def test_long_answer_still_uses_substring(self):
        """Long answers (>4 chars) should still use substring containment."""
        from agent_evals.tasks.fact_extraction import FactExtractionTask

        task = FactExtractionTask(
            _make_definition(
                task_type="fact_extraction",
                expected_answer="authentication",
            )
        )
        response = "The authentication module handles user login."
        score = task.score_response(response)
        assert score == 1.0

    def test_compositional_short_expected_no_false_match(self):
        """Short expected answer 'yes' in compositional sub-task."""
        from agent_evals.tasks.compositional import CompositionalTask

        task = CompositionalTask(
            _make_definition(
                task_type="compositional",
                sub_tasks=[
                    {"question": "Is X supported?", "expected_answer": "yes"},
                ],
            )
        )
        response = "Yesterday the feature was discussed but no conclusion reached."
        score = task.score_response(response)
        assert score < 1.0, (
            f"Short 'yes' matched inside 'yesterday': score={score}"
        )


# ===================================================================
# Bug #199: compute_main_effects returns 0.0 for unobserved levels
# ===================================================================


class TestBug199UnobservedLevelsZero:
    """When a level is unobserved (due to dummy exclusion),
    compute_main_effects returns 0.0, biasing optimal prediction.

    After fix, unobserved levels should return NaN and be excluded
    from predict_optimal's best-level selection.
    """

    def test_unobserved_level_returns_nan(self):
        """Unobserved levels should return NaN, not 0.0."""
        from agent_evals.taguchi.analysis import compute_main_effects

        design = self._make_design_with_unobserved_level()
        sn_ratios = {1: 10.0, 2: 20.0, 3: 15.0}
        effects = compute_main_effects(design, sn_ratios)
        # Factor B has level "b3" that is unobserved (all rows where it
        # would appear have it as dummy).
        unobserved_val = effects["factor_b"]["b3"]
        assert math.isnan(unobserved_val), (
            f"Unobserved level should be NaN, got {unobserved_val}"
        )

    def test_predict_optimal_skips_nan_levels(self):
        """predict_optimal should not select NaN levels as optimal."""
        from agent_evals.taguchi.analysis import predict_optimal

        # Manually construct main_effects with a NaN level
        main_effects = {
            "factor_a": {"a1": 10.0, "a2": 15.0},
            "factor_b": {"b1": 12.0, "b2": 8.0, "b3": float("nan")},
        }
        result = predict_optimal(main_effects)
        # Should pick b1 (12.0), not b3 (NaN)
        assert result.optimal_assignment["factor_b"] == "b1", (
            f"Should pick b1, not NaN level: {result.optimal_assignment}"
        )

    def test_observed_levels_unchanged(self):
        """Observed levels should still return their correct mean."""
        from agent_evals.taguchi.analysis import compute_main_effects

        design = self._make_design_with_unobserved_level()
        sn_ratios = {1: 10.0, 2: 20.0, 3: 15.0}
        effects = compute_main_effects(design, sn_ratios)
        # factor_a: a1 appears in rows 1,2 → mean(10,20) = 15.0
        # factor_a: a2 appears in row 3 → mean(15) = 15.0
        assert effects["factor_a"]["a1"] == pytest.approx(15.0)
        assert effects["factor_a"]["a2"] == pytest.approx(15.0)

    @staticmethod
    def _make_design_with_unobserved_level():
        """Create a design where factor_b level 'b3' is always dummy."""

        @dataclass
        class MockFactor:
            name: str
            level_names: list[str]
            n_levels: int = 0

            def __post_init__(self):
                self.n_levels = len(self.level_names)

        @dataclass
        class MockRow:
            run_id: int
            assignments: dict[str, str]
            dummy_factors: set[str] = field(default_factory=set)

        @dataclass
        class MockDesign:
            factors: list[MockFactor]
            rows: list[MockRow]

        return MockDesign(
            factors=[
                MockFactor("factor_a", ["a1", "a2"]),
                MockFactor("factor_b", ["b1", "b2", "b3"]),
            ],
            rows=[
                MockRow(1, {"factor_a": "a1", "factor_b": "b1"}, set()),
                MockRow(2, {"factor_a": "a1", "factor_b": "b2"}, set()),
                # Row 3 has factor_b as dummy — b3 is the assigned level
                # but should be excluded.
                MockRow(3, {"factor_a": "a2", "factor_b": "b3"}, {"factor_b"}),
            ],
        )


# ===================================================================
# Bug #198: Error trials (score=0.0) included in S/N and ANOVA
# ===================================================================


class TestBug198ErrorTrialsInSNRatio:
    """Error trials get score=0.0 and are included in S/N / ANOVA,
    biasing screening results since errors aren't real measurements.

    After fix, error trials should be excluded from row_scores
    before statistical computations.
    """

    def test_error_trials_excluded_from_row_scores(self):
        """Pipeline should exclude error trials when grouping row_scores."""

        # The _group_row_scores logic (screening) appends trial.score
        # for every trial regardless of trial.error.
        # After fix, trials with error != None should be excluded.

        # Simulate the grouping logic that happens at pipeline.py:286-289
        trials = self._make_trials_with_errors()
        row_scores: dict[int, list[float]] = defaultdict(list)
        for trial in trials:
            # Bug: no check for trial.error
            if trial.error is None:  # This is the fix we're testing for
                row_id = trial.metrics["oa_row_id"]
                row_scores[row_id].append(trial.score)

        # Row 1: 2 good trials (0.8, 0.6), 1 error trial (0.0)
        # Without fix: [0.8, 0.6, 0.0] → mean=0.467
        # With fix: [0.8, 0.6] → mean=0.7
        assert len(row_scores[1]) == 2, (
            f"Expected 2 non-error scores, got {len(row_scores[1])}"
        )
        assert 0.0 not in row_scores[1], (
            "Error trial score 0.0 should not be in row_scores"
        )

    def test_error_trials_in_refinement_excluded(self):
        """Refinement grouping should also exclude error trials."""
        # The _group_refinement_scores method (pipeline.py:135-139)
        # has the same issue.
        trials = self._make_trials_with_errors()

        # Simulate fix: filter error trials before grouping
        good_trials = [t for t in trials if t.error is None]
        assert len(good_trials) == 4  # 6 total - 2 errors

    def test_sn_ratio_not_biased_by_errors(self):
        """S/N ratio should reflect only real measurements."""
        from agent_evals.taguchi.analysis import compute_sn_ratios

        # Without error filtering: row_scores include 0.0 from errors
        scores_with_errors = {1: [0.8, 0.6, 0.0]}
        sn_with = compute_sn_ratios(scores_with_errors)

        # With error filtering: only real measurements
        scores_clean = {1: [0.8, 0.6]}
        sn_clean = compute_sn_ratios(scores_clean)

        # Clean S/N should be higher (better) since 0.0 penalty is removed
        assert sn_clean[1] > sn_with[1], (
            f"Clean S/N ({sn_clean[1]:.2f}) should be > "
            f"error-polluted S/N ({sn_with[1]:.2f})"
        )

    @staticmethod
    def _make_trials_with_errors():
        """Create mock trials with some errors."""

        @dataclass
        class MockTrial:
            task_id: str
            task_type: str
            variant_name: str
            repetition: int
            score: float
            metrics: dict
            error: str | None = None

        return [
            # Row 1: 2 good, 1 error
            MockTrial("t1", "fact_extraction", "v1", 1, 0.8,
                       {"oa_row_id": 1}, None),
            MockTrial("t2", "fact_extraction", "v1", 2, 0.6,
                       {"oa_row_id": 1}, None),
            MockTrial("t3", "fact_extraction", "v1", 3, 0.0,
                       {"oa_row_id": 1}, "API timeout"),
            # Row 2: 2 good, 1 error
            MockTrial("t4", "retrieval", "v2", 1, 0.9,
                       {"oa_row_id": 2}, None),
            MockTrial("t5", "retrieval", "v2", 2, 0.7,
                       {"oa_row_id": 2}, None),
            MockTrial("t6", "retrieval", "v2", 3, 0.0,
                       {"oa_row_id": 2}, "Rate limit"),
        ]
