"""Core Pydantic data models for agent-index.

These models define the data structures for documentation indexing,
transformation pipelines, and configuration management.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocFile(BaseModel):
    """A single documentation file with metadata."""

    rel_path: str  # "guides/auth.md"
    content: str  # raw file content
    size_bytes: int
    token_count: int | None = None  # estimated via tiktoken or heuristic
    tier: str  # "required" | "recommended" | "reference" | custom
    section: str  # grouping label: "API", "Guides"
    priority: int = 0  # for position-aware ordering
    content_hash: str = ""  # SHA-256 for staleness detection
    last_modified: datetime | None = None
    summary: str | None = None  # micro-summary for index metadata
    related: list[str] = Field(default_factory=list)  # related file paths


class DocTree(BaseModel):
    """Collection of documentation files with tree-level metadata."""

    files: dict[str, DocFile]  # keyed by rel_path
    scanned_at: datetime
    source: str  # local path or GitHub URL
    total_tokens: int = 0  # cached sum across all files


class TierConfig(BaseModel):
    """Configuration for a single documentation tier."""

    name: str
    instruction: str
    patterns: list[str] = Field(default_factory=list)  # glob patterns for file assignment


class TransformStep(BaseModel):
    """A single step in the transformation pipeline."""

    type: str  # "passthrough" | "algorithmic" | "llm"
    strategy: str = "default"  # "compressed" | "restructured" | "tagged"
    model: str | None = None  # for LLM steps


class IndexConfig(BaseModel):
    """Full configuration for generating a docs index."""

    index_name: str = "Docs Index"
    marker_id: str = "DOCS"
    root_path: str = "./.docs"
    instruction: str = "Prefer retrieval-led reasoning over pre-training-led reasoning."
    fallback_command: str = ""

    tiers: list[TierConfig] = Field(
        default_factory=lambda: [
            TierConfig(
                name="required",
                instruction="Read these files at the start of every session.",
            ),
            TierConfig(
                name="recommended",
                instruction="Read these files when working on related tasks.",
            ),
            TierConfig(
                name="reference",
                instruction="Consult these files when you need specific details.",
            ),
        ]
    )

    sources: list[dict[str, Any]] = Field(default_factory=list)
    file_extensions: set[str] = Field(default_factory=lambda: {".md", ".mdx", ".rst", ".txt"})
    ignore_patterns: list[str] = Field(
        default_factory=lambda: ["node_modules", "__pycache__", ".git", ".venv"]
    )

    # Output
    output_file: str = ""
    inject_into: str = ""
    format: str = "tiered"  # "flat" | "tiered" | "yaml-index"
    file_strategy: str = "colocate"  # "colocate" (.llms.md next to source) | "directory" (.agent-docs/)

    # Transform pipeline (composable steps)
    transform_steps: list[TransformStep] = Field(
        default_factory=lambda: [TransformStep(type="passthrough")]
    )

    # LLM config (shared by transform and future features)
    llm_provider: str = ""  # "anthropic" | "openai" | "local"
    llm_model: str = ""
    llm_base_url: str = ""  # for local models

    # Cross-tool output
    output_targets: list[str] = Field(default_factory=lambda: ["agents.md"])
    # Options: "agents.md", "claude.md", "cursor-rules", "copilot-instructions"

    max_workers: int = 8
