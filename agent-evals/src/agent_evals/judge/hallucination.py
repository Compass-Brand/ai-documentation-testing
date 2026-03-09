"""Hallucination detection via LLM-as-judge."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class HallucinationResult:
    """Result of hallucination analysis on an agent response."""

    score: float
    hallucination_type: str
    flagged_claims: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "hallucination_score": self.score,
            "hallucination_type": self.hallucination_type,
            "flagged_claims": self.flagged_claims,
        }


def build_hallucination_rubric() -> dict:
    """Build the rubric for hallucination classification.

    Returns a dict with 'system' (the system prompt) and 'criteria'
    (a mapping from category name to description).
    """
    return {
        "system": (
            "You are a hallucination detector. Compare the agent's "
            "response against the source documentation and classify "
            "each claim."
        ),
        "criteria": {
            "grounded": "All claims directly supported by source documents.",
            "extrapolation": (
                "Reasonable inference from source, not explicit."
            ),
            "fabrication": "Claims with no basis in source documentation.",
            "contradiction": (
                "Claims that directly contradict source material."
            ),
        },
    }


def build_hallucination_prompt(
    response: str,
    source_docs: str,
    question: str,
) -> list[dict[str, str]]:
    """Build the LLM prompt messages for hallucination detection.

    Returns a list of message dicts suitable for a chat-completion call.
    """
    rubric = build_hallucination_rubric()
    return [
        {"role": "system", "content": rubric["system"]},
        {
            "role": "user",
            "content": (
                f"## Source Documentation\n{source_docs}\n\n"
                f"## Question Asked\n{question}\n\n"
                f"## Agent Response\n{response}\n\n"
                "## Task\n"
                "Analyze the agent's response against the source "
                "documentation.\n"
                "For each claim in the response, determine if it is:\n"
                "- grounded: directly supported by source\n"
                "- extrapolation: reasonable inference, not explicit\n"
                "- fabrication: no basis in source\n"
                "- contradiction: contradicts source\n\n"
                "Return JSON:\n"
                '{"hallucination_score": 0.0-1.0, '
                '"type": "grounded|extrapolation|fabrication|contradiction", '
                '"flagged_claims": ["claim1", ...]}'
            ),
        },
    ]


def parse_hallucination_result(raw: str) -> HallucinationResult:
    """Parse raw LLM JSON output into a HallucinationResult.

    Extracts the first JSON object from the string. Falls back to a
    default result (score=0.5, type='unknown') on malformed input.
    """
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            return HallucinationResult(
                score=float(data.get("hallucination_score", 0.5)),
                hallucination_type=data.get("type", "unknown"),
                flagged_claims=data.get("flagged_claims", []),
            )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return HallucinationResult(
        score=0.5,
        hallucination_type="unknown",
        flagged_claims=[],
    )
