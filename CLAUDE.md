# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project: AI Documentation Testing

**Description:** AI documentation optimization and evaluation framework - transforms docs into AI-optimized formats and empirically tests which index structures produce the best agent outcomes.

**Project Type:** testing

---

## Components

| Component       | Purpose                                                        |
| --------------- | -------------------------------------------------------------- |
| `agent-index/`  | Scans docs, transforms into `.llms.md` files, generates indexes |
| `agent-evals/`  | Tests 10 format axes across 11 task types with 330+ gold tasks |

---

## Tech stack

| Layer       | Technology                                  |
| ----------- | ------------------------------------------- |
| Language    | Python 3.11+                                |
| Testing     | pytest                                      |
| Packaging   | UV workspace (hatchling build)              |
| LLM Access  | LiteLLM (OpenRouter)                        |
| Validation  | Pydantic v2                                 |
| Statistics  | SciPy, NumPy                                |
| Config      | PyYAML                                      |
| HTTP        | httpx                                       |

---

## Commands

```bash
# Automated setup (installs UV, dependencies, creates .env)
bash scripts/setup.sh          # Linux/macOS
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1  # Windows

# Manual install (UV workspace)
uv sync --dev

# Run all tests
pytest

# Run agent-index tests only
pytest agent-index/tests/

# Run agent-evals tests only
pytest agent-evals/tests/

# Linting
ruff check .

# Type checking
mypy agent-index/src agent-evals/src

# CLI tools
agent-index --local <path>
agent-index --config agent-index.yaml
agent-evals --config <config.yaml>
agent-evals --model openrouter/anthropic/claude-sonnet-4.5 --dry-run
```

### Key CLI flags

```bash
# Ease-of-use flags
agent-evals --verbose              # Debug-level logging
agent-evals --quiet                # Warnings only
agent-evals --continue-on-error    # Skip failed trials
agent-evals --output-format both   # json, csv, or both
agent-evals --display plain        # Progress: rich, plain, none

# Taguchi DOE mode
agent-evals --mode taguchi                     # Run Taguchi screening (L50 OA)
agent-evals --mode taguchi --pipeline auto     # Full pipeline: screening -> confirmation -> refinement
agent-evals --mode taguchi --pipeline auto --top-k 3  # Top 3 factors for refinement

# Multi-model evaluation
agent-evals --mode taguchi --models "model1,model2"   # Model as Taguchi factor

# Observability
agent-evals --store-traces                     # Store prompt/response text in observatory DB

# Resume crashed runs
agent-evals --resume <run_id>                  # Resume a single run
agent-evals --resume-pipeline <pipeline_id>    # Resume a DOE pipeline

# Observatory dashboard
agent-evals --dashboard                        # Enable live dashboard during a run
agent-evals dashboard                          # Start standalone web UI on port 8080
agent-evals dashboard --port 9000              # Custom port
```

---

## Environment variables

```bash
OPENROUTER_API_KEY=sk-or-v1-...   # Required for LLM-based evaluation
```

See `.env.example` for all options.

---

## Standards & guidelines

This project follows Compass Brand standards:

- **Rules:** Inherited from parent [compass-brand/.claude/rules/](https://github.com/Compass-Brand/compass-brand/tree/main/.claude/rules) - coding style, security, testing, git workflow, performance, and agent delegation rules
- **Coverage:** 80%+ overall, 100% on scoring and statistical modules

---

## Development methodology: TDD

All functional code MUST follow Test-Driven Development.

```text
RED -> GREEN -> REFACTOR
```

---

## Git discipline (MANDATORY)

**Commit early, commit often.**

- Commit after completing any file creation or modification
- Maximum 15-20 minutes between commits
- Use conventional commit format: `type: description`

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`
