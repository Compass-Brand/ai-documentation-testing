"""Interactive wizard for building an IndexConfig from user answers.

Since interactive I/O cannot be tested directly, this module uses a
data-flow pattern: WizardAnswers captures user input, and
build_config_from_answers converts it to an IndexConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_index.models import IndexConfig, TierConfig

# Default tier definitions with instructions
_DEFAULT_TIER_DEFS: dict[str, str] = {
    "required": "Read these files at the start of every session.",
    "recommended": "Read these files when working on related tasks.",
    "reference": "Consult these files when you need specific details.",
}


@dataclass
class WizardAnswers:
    """Captures answers from the interactive wizard.

    Attributes:
        project_name: Name of the project.
        doc_locations: List of directory paths containing documentation.
        tiers: List of tier names (e.g., ["required", "recommended", "reference"]).
        output_targets: List of output target names (e.g., ["agents.md", "claude.md"]).
        instruction: Custom instruction for the index.
    """

    project_name: str
    doc_locations: list[str] = field(default_factory=list)
    tiers: list[str] = field(default_factory=lambda: ["required", "recommended", "reference"])
    output_targets: list[str] = field(default_factory=lambda: ["agents.md"])
    instruction: str = "Prefer retrieval-led reasoning over pre-training-led reasoning."


def build_config_from_answers(answers: WizardAnswers) -> IndexConfig:
    """Convert wizard answers to an IndexConfig.

    Maps tier names to TierConfig objects with default instructions,
    and sets the root_path from the first doc_location (or default).

    Args:
        answers: WizardAnswers with user responses.

    Returns:
        Fully constructed IndexConfig.
    """
    # Build tier configs from tier names
    tier_configs: list[TierConfig] = []
    for tier_name in answers.tiers:
        instruction = _DEFAULT_TIER_DEFS.get(
            tier_name,
            f"Files in the {tier_name} tier.",
        )
        tier_configs.append(
            TierConfig(
                name=tier_name,
                instruction=instruction,
            )
        )

    # Determine root path from doc locations
    root_path = answers.doc_locations[0] if answers.doc_locations else "./.docs"

    return IndexConfig(
        index_name=answers.project_name,
        root_path=root_path,
        instruction=answers.instruction,
        tiers=tier_configs,
        output_targets=answers.output_targets,
    )
