"""Axis 12: Agent instruction file variants.

Tests how the presence, verbosity, and topical focus of an agent
instruction file (e.g. CLAUDE.md) affects task performance.

Five **verbosity** levels control overall instruction length:

- ``InstructionNone``: no instructions, doc index only
- ``InstructionMinimal``: <60 lines, non-obvious requirements only
- ``InstructionStandard``: ~150 lines, typical CLAUDE.md content
- ``InstructionVerbose``: 300+ lines, directory trees + style guides + padding
- ``InstructionOverloaded``: 500+ lines, auto-generated module/API lists

Four **ablative** variants isolate individual instruction categories:

- ``InstructionConventionsOnly``: coding conventions (~30 lines)
- ``InstructionArchitectureOnly``: architecture/directory structure (~40 lines)
- ``InstructionDeploymentOnly``: deployment/CI info (~30 lines)
- ``InstructionIrrelevantOnly``: only irrelevant content (style guides, deployment)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

# ---------------------------------------------------------------------------
# Instruction content strings
# ---------------------------------------------------------------------------

_MINIMAL_INSTRUCTIONS = """\
# Agent Instructions

## Key Requirements
- Always read the full file before editing
- Run tests after every change
- Use conventional commit messages (feat, fix, refactor, docs, chore, test)
- Never commit secrets or .env files

## Non-Obvious Constraints
- The test suite requires Python 3.11+
- Integration tests need a running Redis instance on port 6379
- Markdown files must not exceed 200 lines
- All public functions require docstrings with Args/Returns sections
"""

_STANDARD_INSTRUCTIONS = """\
# Agent Instructions

## Project Overview
This is a Python library for document indexing and evaluation.
It uses a UV workspace with two packages: agent-index and agent-evals.

## Tech Stack
- Language: Python 3.11+
- Testing: pytest with pytest-cov
- Packaging: UV workspace (hatchling build)
- Linting: ruff
- Type checking: mypy

## Development Workflow
1. Write a failing test first (TDD)
2. Implement minimal code to pass the test
3. Refactor while keeping tests green
4. Commit with conventional commit messages

## Key Requirements
- Always read the full file before editing
- Run tests after every change
- Use conventional commit messages (feat, fix, refactor, docs, chore, test)
- Never commit secrets or .env files

## Non-Obvious Constraints
- The test suite requires Python 3.11+
- Integration tests need a running Redis instance on port 6379
- Markdown files must not exceed 200 lines
- All public functions require docstrings with Args/Returns sections

## Code Style
- Use snake_case for functions and variables
- Use PascalCase for classes
- Maximum file size: 300 lines
- Maximum function size: 50 lines
- Prefer composition over inheritance

## Testing Standards
- Minimum 80% code coverage
- Critical paths require 100% coverage
- No skipped tests without a documented reason
- Test names: should_<behavior>_when_<condition>

## Directory Structure
```
src/
  agent_evals/
    variants/     # Index format variants
    tasks/        # Task type definitions
    taguchi/      # DOE analysis
    reports/      # Output reports
    context/      # Context strategies
tests/            # Test files mirror src layout
planning/         # Sprint and epic tracking
```

## Git Discipline
- Commit after each logical unit of work
- Maximum 15-20 minutes between commits
- One logical change per commit
- Never commit broken or non-compiling code

## Architecture Decisions
- Variants are auto-discovered via registry decorators
- Tasks use a factory pattern with type dispatch
- The pipeline orchestrates screening, confirmation, and refinement
- Observatory stores run traces in SQLite

## Deployment
- CI runs on GitHub Actions
- Quality checks: ruff + mypy + pytest
- Coverage enforced at 80% in CI
- PRs require passing checks before merge

## Environment Variables
- OPENROUTER_API_KEY: Required for LLM evaluation
- LOG_LEVEL: Optional, defaults to INFO
- OBSERVATORY_DB: Optional, defaults to observatory.db
"""

_VERBOSE_PADDING_LINES = [
    f"# Note {i}: This is additional context line {i} providing supplementary "
    f"information about the project's coding standards and practices."
    for i in range(1, 101)
]

_VERBOSE_INSTRUCTIONS = """\
# Agent Instructions

## Project Overview
This is a Python library for document indexing and evaluation.
It uses a UV workspace with two packages: agent-index and agent-evals.

## Tech Stack
- Language: Python 3.11+
- Testing: pytest with pytest-cov
- Packaging: UV workspace (hatchling build)
- Linting: ruff
- Type checking: mypy

## Development Workflow
1. Write a failing test first (TDD)
2. Implement minimal code to pass the test
3. Refactor while keeping tests green
4. Commit with conventional commit messages

## Key Requirements
- Always read the full file before editing
- Run tests after every change
- Use conventional commit messages (feat, fix, refactor, docs, chore, test)
- Never commit secrets or .env files

## Code Style Guide
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_SNAKE_CASE for constants
- Maximum file size: 300 lines
- Maximum function size: 50 lines
- Prefer composition over inheritance
- Use type hints on all function signatures
- Docstrings must follow Google style

## Directory Structure
```
project-root/
  agent-index/
    src/
      agent_index/
        scanner.py
        models.py
        renderer.py
    tests/
  agent-evals/
    src/
      agent_evals/
        variants/
        tasks/
        taguchi/
        reports/
        context/
        observatory/
    tests/
  planning/
    backlog/
    sprints/
    epics/
    decisions/
```

## Testing Standards
- Minimum 80% code coverage
- Critical paths require 100% coverage
- No skipped tests without a documented reason
- Test names: should_<behavior>_when_<condition>
- Use fixtures for shared test state
- Clean up test data between tests

## Supplementary Notes
""" + "\n".join(_VERBOSE_PADDING_LINES)

_OVERLOADED_MODULE_LINES = [
    f"- `module_{i:03d}`: Auto-generated module {i} providing utilities "
    f"for processing type-{i} data transformations"
    for i in range(1, 101)
]

_OVERLOADED_API_LINES = [
    f"- `GET /api/v1/resource_{i:03d}`: Returns resource {i} data "
    f"with pagination and filtering support"
    for i in range(1, 101)
]

_OVERLOADED_INSTRUCTIONS = """\
# Agent Instructions

## Project Overview
This is a Python library for document indexing and evaluation.

## Key Requirements
- Always read the full file before editing
- Run tests after every change

## Auto-Generated Module Registry

""" + "\n".join(_OVERLOADED_MODULE_LINES) + """

## Auto-Generated API Endpoints

""" + "\n".join(_OVERLOADED_API_LINES)

_CONVENTIONS_ONLY_INSTRUCTIONS = """\
# Coding Conventions

## Naming Conventions
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_SNAKE_CASE for constants
- Prefix private members with underscore

## Import Conventions
- Group imports: stdlib, third-party, local
- Use absolute imports over relative imports
- Sort imports alphabetically within groups

## Docstring Convention
- All public functions require docstrings
- Use Google-style docstring format
- Include Args, Returns, and Raises sections

## Formatting Rules
- Maximum line length: 88 characters (ruff default)
- Use trailing commas in multi-line collections
- Prefer f-strings over .format() or % formatting
"""

_ARCHITECTURE_ONLY_INSTRUCTIONS = """\
# Architecture Overview

## Directory Structure
```
src/
  agent_evals/
    variants/     # Index format variants (auto-discovered)
    tasks/        # Task type definitions (factory pattern)
    taguchi/      # Design of experiments analysis
    reports/      # Output report generators
    context/      # Context delivery strategies
    observatory/  # Run trace storage (SQLite)
    pipeline.py   # DOE pipeline orchestration
    runner.py     # Task execution with ThreadPoolExecutor
    cli.py        # Command-line interface
```

## Key Architecture Decisions
- Variants use decorator-based registry for auto-discovery
- Tasks use a factory pattern with type dispatch
- Pipeline orchestrates screening -> confirmation -> refinement
- Observatory stores traces in SQLite for post-hoc analysis
- Context strategies are pluggable via ABC interface

## Component Dependencies
- CLI -> Pipeline -> Runner -> Tasks + Variants
- Observatory is orthogonal (write-only from Runner)
- Reports read from Observatory DB
"""

_DEPLOYMENT_ONLY_INSTRUCTIONS = """\
# Deployment and CI

## CI Pipeline
- GitHub Actions runs on every push and PR
- Quality checks: ruff lint + mypy type-check + pytest
- Coverage threshold enforced at 80% in CI
- PRs require all checks passing before merge

## Deployment Process
- Deploy to staging via `deploy.sh --env staging`
- Production deploy requires manual approval
- Rollback with `deploy.sh --rollback <version>`
- Health checks run automatically post-deploy

## Environment Configuration
- Staging: OPENROUTER_API_KEY from GitHub Secrets
- Production: API keys from Infisical vault
- LOG_LEVEL defaults to INFO in production
"""

_IRRELEVANT_INSTRUCTIONS = """\
# Project Guidelines

## Code Style and Formatting
- Use black for Python formatting with default settings
- Use isort for import sorting
- Style checks are enforced in pre-commit hooks
- Line length is 88 characters (black default)

## CI/CD Pipeline Details
- GitHub Actions workflow runs on push to main and develop
- Deploy to staging automatically on develop merge
- Production deploy requires manual approval gate
- Rollback procedure documented in ops runbook

## Team Communication
- Use Slack #dev channel for async questions
- Stand-ups at 9:30 AM EST daily
- Sprint retrospectives every other Friday
- Design review meetings on Wednesdays

## Brand Guidelines
- Use Compass Brand color palette (#1E40AF primary)
- Logo must have 24px minimum clear space
- Font: Inter for headings, Source Sans Pro for body
- Follow Material Design 3 component guidelines
"""

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _render_doc_index(doc_tree: DocTree) -> str:
    """Render a standard documentation index section from a DocTree.

    Lists all files grouped by section with path, tier, token count,
    and summary.

    Args:
        doc_tree: Documentation tree to render.

    Returns:
        Markdown string starting with ``# Documentation Index``.
    """
    lines: list[str] = ["# Documentation Index"]

    if not doc_tree.files:
        return "\n".join(lines)

    # Group files by section
    sections: dict[str, list[str]] = {}
    section_order: list[str] = []
    for rel_path in sorted(doc_tree.files):
        doc = doc_tree.files[rel_path]
        section = doc.section
        if section not in sections:
            sections[section] = []
            section_order.append(section)
        tokens = doc.token_count if doc.token_count is not None else 0
        summary = doc.summary if doc.summary else ""
        sections[section].append(
            f"- {rel_path} ({doc.tier}, ~{tokens} tokens) -- {summary}"
        )

    for section_name in section_order:
        lines.append("")
        lines.append(f"## {section_name}")
        lines.extend(sections[section_name])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verbosity variants
# ---------------------------------------------------------------------------


@register_variant
class InstructionNone(IndexVariant):
    """No agent instructions -- doc index only.

    Baseline for measuring instruction impact: the agent receives only
    the documentation index with no behavioural guidance.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-none",
            axis=12,
            category="agent-instruction",
            description="No agent instructions, doc index only.",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _render_doc_index(doc_tree)


@register_variant
class InstructionMinimal(IndexVariant):
    """Minimal agent instructions (<60 lines).

    Contains only non-obvious requirements that an agent would not
    infer from the codebase alone.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-minimal",
            axis=12,
            category="agent-instruction",
            description="Minimal instructions (<60 lines), non-obvious requirements only.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _MINIMAL_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionStandard(IndexVariant):
    """Standard agent instructions (~150 lines).

    Typical CLAUDE.md content covering project overview, tech stack,
    development workflow, code style, and testing standards.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-standard",
            axis=12,
            category="agent-instruction",
            description="Standard ~150-line instructions (typical CLAUDE.md).",
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _STANDARD_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionVerbose(IndexVariant):
    """Verbose agent instructions (300+ lines).

    Includes directory trees, expanded style guides, and 100 padding
    lines of supplementary notes to test attention dilution.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-verbose",
            axis=12,
            category="agent-instruction",
            description="Verbose 300+ line instructions with padding.",
            token_estimate=2000,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _VERBOSE_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionOverloaded(IndexVariant):
    """Overloaded agent instructions (500+ lines).

    Contains auto-generated module lists (100 entries) and API endpoint
    lists (100 entries) to test information overload effects.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-overloaded",
            axis=12,
            category="agent-instruction",
            description="Overloaded 500+ line instructions with auto-generated lists.",
            token_estimate=4000,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _OVERLOADED_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)


# ---------------------------------------------------------------------------
# Ablative variants
# ---------------------------------------------------------------------------


@register_variant
class InstructionConventionsOnly(IndexVariant):
    """Only coding conventions (~30 lines).

    Isolates the effect of naming/formatting conventions on agent
    performance, excluding architecture and deployment information.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-conventions-only",
            axis=12,
            category="agent-instruction",
            description="Coding conventions only (~30 lines).",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        return (
            _CONVENTIONS_ONLY_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)
        )


@register_variant
class InstructionArchitectureOnly(IndexVariant):
    """Only architecture and directory structure (~40 lines).

    Isolates the effect of structural knowledge on agent performance,
    excluding coding conventions and deployment details.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-architecture-only",
            axis=12,
            category="agent-instruction",
            description="Architecture/directory structure only (~40 lines).",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        return (
            _ARCHITECTURE_ONLY_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)
        )


@register_variant
class InstructionDeploymentOnly(IndexVariant):
    """Only deployment and CI information (~30 lines).

    Isolates the effect of deployment knowledge on agent performance,
    excluding coding conventions and architecture details.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-deployment-only",
            axis=12,
            category="agent-instruction",
            description="Deployment/CI info only (~30 lines).",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        return (
            _DEPLOYMENT_ONLY_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)
        )


@register_variant
class InstructionIrrelevantOnly(IndexVariant):
    """Only irrelevant content (style guides, deployment, CI/CD).

    Control variant containing only information unlikely to help with
    documentation-related tasks -- tests whether irrelevant instructions
    actively harm performance compared to no instructions.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-irrelevant-only",
            axis=12,
            category="agent-instruction",
            description="Only irrelevant content (style, deployment, CI/CD).",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        return (
            _IRRELEVANT_INSTRUCTIONS + "\n\n" + _render_doc_index(doc_tree)
        )
