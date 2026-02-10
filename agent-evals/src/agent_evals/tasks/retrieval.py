"""Retrieval task type for evaluating file identification accuracy.

Scores responses using F-beta (beta=2) to weight recall over precision,
since missing a needed document costs more than including an extra one.

Path normalization handles case differences, leading ``./``, and trailing
slashes.  Fuzzy matching awards partial credit when the basename matches
even if the directory differs.
"""

from __future__ import annotations

import os
import re

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# Pattern to match file paths with common extensions (case-insensitive)
_FILE_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:[\w./-]+/)?[\w.-]+\.(?:md|py|yaml|yml|json|toml|txt|rst|html)",
    re.IGNORECASE,
)


def _normalize_path(path: str) -> str:
    """Normalize a file path for comparison.

    Strips leading ``./``, converts to lowercase, normalizes separators,
    and removes trailing slashes.
    """
    p = path.strip()
    if p.startswith("./"):
        p = p[2:]
    p = p.replace("\\", "/").rstrip("/").lower()
    return p


class RetrievalTask(EvalTask):
    """Task type for evaluating file retrieval accuracy.

    Extracts file paths from the LLM response and computes F-beta (beta=2)
    against the expected file list. Beta=2 weights recall over precision.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_files: list[str] = meta.get("expected_files", [])
        self.evidence_passage: str = meta.get("evidence_passage", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for file retrieval evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that identifies relevant files "
                    "from a documentation index. Given a question, list the "
                    "file paths that are most relevant to answering it.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using F-beta (beta=2) against expected files.

        Extracts file paths from the response text using regex, normalizes
        them for comparison, then computes F-beta score.  When exact
        (normalized) matching fails for an expected file, basename matching
        provides partial credit (counted as 0.5 of a true positive).

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            F-beta score between 0.0 and 1.0.
        """
        raw_extracted = set(_FILE_PATH_PATTERN.findall(response))
        extracted_norm = {_normalize_path(p) for p in raw_extracted}
        expected_norm = {_normalize_path(p) for p in self.expected_files}

        # Edge cases
        if not expected_norm and not extracted_norm:
            return 1.0
        if not expected_norm and extracted_norm:
            return 0.0
        if expected_norm and not extracted_norm:
            return 0.0

        # Exact normalized matches
        exact_matches = expected_norm & extracted_norm

        # Fuzzy: basename matching for unmatched expected files
        unmatched_expected = expected_norm - exact_matches
        unmatched_extracted = extracted_norm - exact_matches
        fuzzy_hits = 0.0
        for exp in unmatched_expected:
            exp_basename = os.path.basename(exp)
            for ext in unmatched_extracted:
                if os.path.basename(ext) == exp_basename:
                    fuzzy_hits += 0.5
                    break

        true_positives = len(exact_matches) + fuzzy_hits
        precision = true_positives / len(extracted_norm) if extracted_norm else 0.0
        recall = true_positives / len(expected_norm) if expected_norm else 0.0

        if precision + recall == 0.0:
            return 0.0

        beta = 2.0
        beta_sq = beta * beta
        fbeta = (1.0 + beta_sq) * precision * recall / (beta_sq * precision + recall)

        return max(0.0, min(1.0, fbeta))


register_task_type("retrieval", RetrievalTask)
