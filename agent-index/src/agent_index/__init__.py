"""agent-index: AI documentation optimizer and tiered index generator."""

from agent_index.autodetect import auto_detect, generate_config_yaml
from agent_index.config import ConfigError, find_config, load_config
from agent_index.models import (
    DocFile,
    DocTree,
    IndexConfig,
    TierConfig,
    TransformStep,
)
from agent_index.output import (
    inject_into_file,
    render_claude_md,
    render_copilot_instructions,
    render_cursor_rules,
    render_for_target,
    render_index,
)
from agent_index.scaffold import scaffold_project
from agent_index.scanner import GitHubError, scan_github, scan_local
from agent_index.tiers import assign_tiers, group_by_section, sort_files_bluf
from agent_index.transform import (
    TransformPipeline,
    TransformResult,
    TransformState,
    algorithmic_compress,
    load_state,
    passthrough,
    save_state,
)
from agent_index.validate import ValidationResult, validate_index
from agent_index.wizard import WizardAnswers, build_config_from_answers

__version__ = "0.1.0"

__all__ = [
    "ConfigError",
    "DocFile",
    "DocTree",
    "GitHubError",
    "IndexConfig",
    "TierConfig",
    "TransformPipeline",
    "TransformResult",
    "TransformState",
    "TransformStep",
    "ValidationResult",
    "WizardAnswers",
    "algorithmic_compress",
    "assign_tiers",
    "auto_detect",
    "build_config_from_answers",
    "find_config",
    "generate_config_yaml",
    "group_by_section",
    "inject_into_file",
    "load_config",
    "load_state",
    "passthrough",
    "render_claude_md",
    "render_copilot_instructions",
    "render_cursor_rules",
    "render_for_target",
    "render_index",
    "save_state",
    "scaffold_project",
    "scan_github",
    "scan_local",
    "sort_files_bluf",
    "validate_index",
    "__version__",
]
