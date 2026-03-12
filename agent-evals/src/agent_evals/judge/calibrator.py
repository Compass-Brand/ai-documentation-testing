"""LLM-as-judge calibration module.

Provides data models and functions for calibrating LLM judge scorers against
gold standard human annotations.  Computes inter-rater agreement metrics
(Cohen's kappa, Spearman rho, Kendall tau) and aggregates per-task-type
breakdowns to flag task types that fall below quality thresholds.

Design targets (from DESIGN.md / schema.yaml):
- Cohen's kappa >= 0.70  (categorical agreement)
- Spearman rho  >= 0.80  (rank correlation)
- Minimum 30 gold examples per task type
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from scipy import stats  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class JudgeScore:
    """A single judge's score for one example."""

    example_id: str
    judge_model: str
    score: float  # 0.0 - 1.0
    rationale: str
    raw_response: str


@dataclass
class CalibrationResult:
    """Result of calibrating a judge against gold standard."""

    judge_model: str
    total_examples: int
    cohens_kappa: float  # Target >= 0.70
    spearman_rho: float  # Target >= 0.80
    kendalls_tau: float  # Report alongside Spearman
    mean_absolute_error: float
    per_type_kappa: dict[str, float] = field(default_factory=dict)
    per_type_spearman: dict[str, float] = field(default_factory=dict)
    flagged_types: list[str] = field(default_factory=list)
    passed: bool = False


@dataclass
class GoldExample:
    """A gold standard example with human annotation."""

    example_id: str
    task_type: str
    difficulty: str
    question: str
    response: str
    human_score: float
    human_rationale: str


# ---------------------------------------------------------------------------
# Agreement metrics
# ---------------------------------------------------------------------------


def _bin_scores(scores: list[float], bins: int = 5) -> list[int]:
    """Bin continuous [0, 1] scores into ``bins`` ordinal categories.

    Bin edges: [0, 1/bins), [1/bins, 2/bins), ..., [(bins-1)/bins, 1.0].
    Scores exactly equal to 1.0 are placed in the last bin.
    """
    binned: list[int] = []
    for s in scores:
        b = int(s * bins)
        if b >= bins:
            b = bins - 1
        binned.append(b)
    return binned


def compute_cohens_kappa(
    scores_a: list[float],
    scores_b: list[float],
    bins: int = 5,
) -> float:
    """Compute Cohen's kappa between two sets of scores.

    Bins continuous scores into ``bins`` categories for kappa computation.
    Uses quadratic weighting for ordinal data.

    Returns 0.0 for degenerate inputs (empty, single-value, or no variance).
    """
    if len(scores_a) != len(scores_b):
        msg = "scores_a and scores_b must have the same length"
        raise ValueError(msg)

    if len(scores_a) <= 1:
        return 0.0

    binned_a = _bin_scores(scores_a, bins)
    binned_b = _bin_scores(scores_b, bins)

    # If there is no variation in either set, kappa is undefined -> 0.0
    if len(set(binned_a)) <= 1 and len(set(binned_b)) <= 1:
        # If both are identical constants, perfect agreement in a trivial sense
        if binned_a == binned_b:
            return 1.0
        return 0.0

    # Build confusion matrix
    matrix = np.zeros((bins, bins), dtype=np.float64)
    for a_val, b_val in zip(binned_a, binned_b, strict=True):
        matrix[a_val][b_val] += 1

    n = float(len(binned_a))

    # Quadratic weight matrix: w_ij = (i - j)^2 / (bins - 1)^2
    weights = np.zeros((bins, bins), dtype=np.float64)
    for i in range(bins):
        for j in range(bins):
            weights[i][j] = ((i - j) ** 2) / ((bins - 1) ** 2)

    # Expected matrix under independence
    row_sums = matrix.sum(axis=1)
    col_sums = matrix.sum(axis=0)
    expected = np.outer(row_sums, col_sums) / n

    # Weighted observed and expected disagreement
    observed_disagreement = float(np.sum(weights * matrix) / n)
    expected_disagreement = float(np.sum(weights * expected) / n)

    if expected_disagreement == 0.0:
        return 1.0

    kappa = 1.0 - (observed_disagreement / expected_disagreement)
    return float(kappa)


def compute_spearman(
    scores_a: list[float],
    scores_b: list[float],
) -> float:
    """Compute Spearman rank correlation coefficient.

    Returns 0.0 for degenerate inputs (empty, single-value, or constant).
    """
    if len(scores_a) != len(scores_b):
        msg = "scores_a and scores_b must have the same length"
        raise ValueError(msg)

    if len(scores_a) <= 1:
        return 0.0

    # Constant arrays produce NaN from scipy; return 0.0 instead
    if len(set(scores_a)) <= 1 or len(set(scores_b)) <= 1:
        return 0.0

    rho, _ = stats.spearmanr(scores_a, scores_b)
    if np.isnan(rho):
        return 0.0
    return float(rho)


def compute_kendall_tau(
    scores_a: list[float],
    scores_b: list[float],
) -> float:
    """Compute Kendall's tau rank correlation coefficient.

    Returns 0.0 for degenerate inputs (empty, single-value, or constant).
    """
    if len(scores_a) != len(scores_b):
        msg = "scores_a and scores_b must have the same length"
        raise ValueError(msg)

    if len(scores_a) <= 1:
        return 0.0

    if len(set(scores_a)) <= 1 or len(set(scores_b)) <= 1:
        return 0.0

    tau, _ = stats.kendalltau(scores_a, scores_b)
    if np.isnan(tau):
        return 0.0
    return float(tau)


def compute_mean_absolute_error(
    predicted: list[float],
    actual: list[float],
) -> float:
    """Compute mean absolute error between predicted and actual scores.

    Returns 0.0 for empty inputs.
    """
    if len(predicted) != len(actual):
        msg = "predicted and actual must have the same length"
        raise ValueError(msg)

    if len(predicted) == 0:
        return 0.0

    return float(np.mean(np.abs(np.array(predicted) - np.array(actual))))


# ---------------------------------------------------------------------------
# Judge prompting
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = """\
You are an expert evaluator assessing the quality of an AI assistant's response.

## Task Type: {task_type}

## Scoring Rubric
{rubric}

## Instructions
1. Read the question and the response carefully.
2. Think step-by-step about the response quality.
3. Consider correctness, completeness, and conciseness.
4. Penalize unnecessarily verbose responses that pad length without adding value.
5. Provide your reasoning BEFORE giving a numeric score.

## Output Format
You MUST output exactly this format:

RATIONALE: <your step-by-step reasoning>
SCORE: <a single number between 0.0 and 1.0>
"""

_REFERENCE_RUBRICS: dict[str, str] = {
    "code_generation": (
        "Score the code against the provided reference solution and test "
        "criteria. Check: (1) Does it define the expected entry point? "
        "(2) Does it match the test patterns? (3) Is it functionally "
        "equivalent to the reference? (4) Does it avoid forbidden patterns? "
        "Score 1.0 for a correct implementation, 0.0 for non-functional code."
    ),
    "compositional": (
        "Score the response against the expected answer. Check that ALL "
        "sub-parts of the question are addressed correctly. Score based on "
        "the fraction of sub-answers that match the expected answer."
    ),
    "agentic": (
        "Score the response against the expected answer. Evaluate the "
        "reasoning chain, tool usage, and final answer. Compare against "
        "the reference to determine correctness, not just plausibility."
    ),
}

_DEFAULT_RUBRICS: dict[str, str] = {
    "retrieval": (
        "Evaluate whether the response correctly retrieves and presents the "
        "relevant information from the documentation. Score 1.0 for a fully "
        "correct retrieval, 0.0 for completely wrong or missing information."
    ),
    "fact_extraction": (
        "Evaluate whether the response accurately extracts the requested facts. "
        "Score 1.0 for perfect extraction with no errors, 0.0 for completely "
        "wrong or fabricated facts."
    ),
    "code_generation": (
        "Evaluate the generated code for correctness, completeness, and proper "
        "use of APIs. Score 1.0 for fully correct, runnable code that solves "
        "the task, 0.0 for non-functional or irrelevant code."
    ),
    "agentic": (
        "Evaluate the response for correct tool usage, reasoning chain, and "
        "task completion. Score 1.0 for a fully correct agentic trajectory, "
        "0.0 for completely wrong tool usage or reasoning."
    ),
    "multi_hop": (
        "Evaluate whether the response correctly chains multiple pieces of "
        "information. Score 1.0 for a fully correct multi-hop reasoning chain, "
        "0.0 for failure to connect relevant information."
    ),
    "negative": (
        "Evaluate whether the response correctly identifies that the question "
        "cannot be answered from the given context. Score 1.0 for properly "
        "declining with explanation, 0.0 for fabricating an answer."
    ),
    "compositional": (
        "Evaluate whether the response correctly handles all sub-parts of a "
        "complex question. Score 1.0 for addressing all parts correctly, "
        "0.0 for missing or incorrect sub-answers."
    ),
    "robustness": (
        "Evaluate whether the response maintains correctness despite input "
        "perturbations. Score 1.0 for a robust correct answer, 0.0 for "
        "being misled by the perturbation."
    ),
    "disambiguation": (
        "Evaluate whether the response correctly identifies and resolves "
        "ambiguity in the question. Score 1.0 for proper disambiguation, "
        "0.0 for ignoring the ambiguity or picking the wrong interpretation."
    ),
    "conflicting": (
        "Evaluate whether the response correctly handles conflicting "
        "information in the context. Score 1.0 for properly acknowledging "
        "and resolving the conflict, 0.0 for silently picking one side."
    ),
    "efficiency": (
        "Evaluate whether the response is concise and efficient while "
        "remaining correct. Score 1.0 for an optimal response, 0.0 for "
        "excessively verbose or incorrect output."
    ),
}

_GENERIC_RUBRIC = (
    "Evaluate the response for correctness, completeness, and conciseness. "
    "Score 1.0 for a perfect response, 0.0 for a completely wrong response."
)


def build_judge_prompt(
    task_type: str,
    question: str,
    response: str,
    rubric: str | None = None,
    *,
    expected_answer: str | None = None,
    canonical_solution: str | None = None,
    test_criteria: dict | None = None,
) -> list[dict[str, str]]:
    """Build the prompt for the LLM judge.

    When reference material (expected_answer, canonical_solution,
    test_criteria) is provided, the judge performs reference-based
    evaluation — scoring the response against the ground truth rather
    than relying on subjective quality assessment.
    """
    has_reference = any([expected_answer, canonical_solution, test_criteria])

    if has_reference:
        effective_rubric = rubric or _REFERENCE_RUBRICS.get(
            task_type, _DEFAULT_RUBRICS.get(task_type, _GENERIC_RUBRIC)
        )
    else:
        effective_rubric = rubric or _DEFAULT_RUBRICS.get(task_type, _GENERIC_RUBRIC)

    system_msg = _SYSTEM_TEMPLATE.format(
        task_type=task_type,
        rubric=effective_rubric,
    )

    # Build user message with optional reference sections
    parts = [f"## Question\n{question}"]

    if expected_answer:
        parts.append(f"## Expected Answer\n{expected_answer}")

    if canonical_solution:
        parts.append(f"## Reference Solution\n```\n{canonical_solution}\n```")

    if test_criteria:
        criteria_lines: list[str] = []
        if "entry_point" in test_criteria:
            criteria_lines.append(f"- Entry Point: `{test_criteria['entry_point']}`")
        if "test_patterns" in test_criteria:
            for pat in test_criteria["test_patterns"]:
                criteria_lines.append(f"- Must contain: `{pat}`")
        if "libs" in test_criteria:
            criteria_lines.append(
                f"- Expected libraries: {', '.join(test_criteria['libs'])}"
            )
        if "forbidden_patterns" in test_criteria:
            for pat in test_criteria["forbidden_patterns"]:
                criteria_lines.append(f"- Must NOT contain: `{pat}`")
        if criteria_lines:
            parts.append("## Test Criteria\n" + "\n".join(criteria_lines))

    parts.append(f"## Response to Evaluate\n{response}")

    user_msg = "\n\n".join(parts)

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


# ---------------------------------------------------------------------------
# Judge metadata extraction
# ---------------------------------------------------------------------------


def extract_judge_metadata(task_type: str, meta: dict) -> dict:
    """Extract reference metadata for judge prompts from task metadata.

    Returns kwargs suitable for passing to ``build_judge_prompt()``.
    """
    kwargs: dict = {}
    if task_type == "code_generation":
        kwargs["expected_answer"] = meta.get("expected_answer")
        kwargs["canonical_solution"] = meta.get("canonical_solution")
        test_criteria: dict = {}
        if meta.get("entry_point"):
            test_criteria["entry_point"] = meta["entry_point"]
        if meta.get("test"):
            test_criteria["test_patterns"] = [
                p for p in meta["test"].split("\n") if p.strip()
            ]
        if meta.get("libs"):
            test_criteria["libs"] = meta["libs"]
        if meta.get("forbidden_patterns"):
            test_criteria["forbidden_patterns"] = meta["forbidden_patterns"]
        if test_criteria:
            kwargs["test_criteria"] = test_criteria

    elif task_type == "compositional":
        expected_answers = meta.get("expected_answers", [])
        sub_questions = meta.get("sub_questions", [])
        if expected_answers:
            parts = []
            for i, (q, a) in enumerate(
                zip(sub_questions, expected_answers), 1
            ):
                parts.append(f"{i}. {q}: {a}")
            kwargs["expected_answer"] = "\n".join(parts)

    elif task_type == "agentic":
        expected_tools = meta.get("expected_tools", [])
        files = meta.get("files", {})
        fail_to_pass = meta.get("FAIL_TO_PASS", [])
        ref_parts = []
        if expected_tools:
            ref_parts.append(
                "Expected tools: " + ", ".join(
                    t.get("name", "") if isinstance(t, dict) else str(t)
                    for t in expected_tools
                )
            )
        if files:
            ref_parts.append(
                "Key files: " + ", ".join(files.keys())
            )
        if fail_to_pass:
            ref_parts.append(
                "Must-pass tests: " + ", ".join(fail_to_pass)
            )
        if ref_parts:
            kwargs["expected_answer"] = "\n".join(ref_parts)

    else:
        # Generic: pass expected_answer if present
        if meta.get("expected_answer"):
            kwargs["expected_answer"] = meta["expected_answer"]

    return kwargs


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_SCORE_PATTERN = re.compile(
    r"^\s*SCORE\s*:\s*([0-9]*\.?[0-9]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_RATIONALE_PATTERN = re.compile(
    r"RATIONALE\s*:\s*(.*?)(?=\n\s*SCORE\s*:)",
    re.IGNORECASE | re.DOTALL,
)


def parse_judge_response(response: str) -> tuple[float, str]:
    """Extract score and rationale from judge's response.

    Expected format from judge::

        RATIONALE: <reasoning>
        SCORE: <0.0-1.0>

    Returns
    -------
    tuple[float, str]
        ``(score, rationale)``.

    Raises
    ------
    ValueError
        If the response cannot be parsed or the score is out of range.
    """
    score_match = _SCORE_PATTERN.search(response)
    if score_match is None:
        msg = (
            "Could not parse SCORE from judge response. "
            "Expected format: 'SCORE: <0.0-1.0>'"
        )
        raise ValueError(msg)

    score = float(score_match.group(1))
    if score < 0.0 or score > 1.0:
        msg = f"Score {score} is out of range [0.0, 1.0]"
        raise ValueError(msg)

    rationale_match = _RATIONALE_PATTERN.search(response)
    rationale = rationale_match.group(1).strip() if rationale_match else ""

    return score, rationale


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def calibrate(
    gold_examples: list[GoldExample],
    judge_scores: list[JudgeScore],
    kappa_threshold: float = 0.70,
    spearman_threshold: float = 0.80,
    min_examples_per_type: int = 30,
) -> CalibrationResult:
    """Calibrate judge scores against gold standard.

    Computes overall and per-task-type agreement metrics.
    Flags task types below threshold.

    Parameters
    ----------
    gold_examples:
        Gold standard examples with human annotations.
    judge_scores:
        Judge scores to calibrate against the gold standard.
    kappa_threshold:
        Minimum Cohen's kappa for a task type to pass.
    spearman_threshold:
        Minimum Spearman rho for a task type to pass.
    min_examples_per_type:
        Minimum number of gold examples required per task type.
        Set to 0 to disable the check. Default is 30 per the
        design target.

    Returns
    -------
    CalibrationResult
        Aggregated calibration metrics with per-type breakdowns.

    Raises
    ------
    ValueError
        If any task type has fewer than *min_examples_per_type* examples.
    """
    if not gold_examples or not judge_scores:
        return CalibrationResult(
            judge_model=judge_scores[0].judge_model if judge_scores else "",
            total_examples=0,
            cohens_kappa=0.0,
            spearman_rho=0.0,
            kendalls_tau=0.0,
            mean_absolute_error=0.0,
            per_type_kappa={},
            per_type_spearman={},
            flagged_types=[],
            passed=False,
        )

    # Validate minimum sample size per task type
    if min_examples_per_type > 0:
        from collections import Counter

        type_counts = Counter(g.task_type for g in gold_examples)
        for task_type, count in sorted(type_counts.items()):
            if count < min_examples_per_type:
                msg = (
                    f"Task type '{task_type}' has only {count} gold examples, "
                    f"but min_examples_per_type requires {min_examples_per_type}"
                )
                raise ValueError(msg)

    # Build lookup: example_id -> gold example
    gold_lookup: dict[str, GoldExample] = {g.example_id: g for g in gold_examples}

    # Build lookup: example_id -> judge score
    judge_lookup: dict[str, JudgeScore] = {j.example_id: j for j in judge_scores}

    # Match on common example IDs
    common_ids = sorted(set(gold_lookup.keys()) & set(judge_lookup.keys()))

    if not common_ids:
        return CalibrationResult(
            judge_model=judge_scores[0].judge_model,
            total_examples=0,
            cohens_kappa=0.0,
            spearman_rho=0.0,
            kendalls_tau=0.0,
            mean_absolute_error=0.0,
            per_type_kappa={},
            per_type_spearman={},
            flagged_types=[],
            passed=False,
        )

    human_scores: list[float] = []
    judge_scores_matched: list[float] = []

    # Group by task type for per-type metrics
    type_human: dict[str, list[float]] = defaultdict(list)
    type_judge: dict[str, list[float]] = defaultdict(list)

    for eid in common_ids:
        gold = gold_lookup[eid]
        judge = judge_lookup[eid]
        human_scores.append(gold.human_score)
        judge_scores_matched.append(judge.score)
        type_human[gold.task_type].append(gold.human_score)
        type_judge[gold.task_type].append(judge.score)

    # Overall metrics
    overall_kappa = compute_cohens_kappa(human_scores, judge_scores_matched)
    overall_spearman = compute_spearman(human_scores, judge_scores_matched)
    overall_tau = compute_kendall_tau(human_scores, judge_scores_matched)
    overall_mae = compute_mean_absolute_error(judge_scores_matched, human_scores)

    # Per-type metrics
    per_type_kappa: dict[str, float] = {}
    per_type_spearman: dict[str, float] = {}
    flagged_types: list[str] = []

    for task_type in sorted(type_human.keys()):
        h = type_human[task_type]
        j = type_judge[task_type]
        tk = compute_cohens_kappa(h, j)
        ts = compute_spearman(h, j)
        per_type_kappa[task_type] = tk
        per_type_spearman[task_type] = ts
        if tk < kappa_threshold or ts < spearman_threshold:
            flagged_types.append(task_type)

    passed = overall_kappa >= kappa_threshold and overall_spearman >= spearman_threshold

    return CalibrationResult(
        judge_model=judge_scores[0].judge_model,
        total_examples=len(common_ids),
        cohens_kappa=overall_kappa,
        spearman_rho=overall_spearman,
        kendalls_tau=overall_tau,
        mean_absolute_error=overall_mae,
        per_type_kappa=per_type_kappa,
        per_type_spearman=per_type_spearman,
        flagged_types=flagged_types,
        passed=passed,
    )
