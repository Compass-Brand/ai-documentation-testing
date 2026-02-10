# AI Documentation Testing

AI documentation optimization and evaluation framework. Transforms docs into
AI-optimized formats and empirically tests which index structures produce the
best agent outcomes.

## Quick Start

```bash
# Install
uv sync --dev

# Set your API key
cp .env.example .env
# Edit .env with your OpenRouter key from https://openrouter.ai/keys

# Run a minimal evaluation
agent-evals --config examples/minimal-config.yaml

# Run tests
pytest
```

## Architecture

Two complementary packages in a UV workspace:

| Package | Purpose |
|---------|---------|
| `agent-index/` | Scans documentation, transforms into `.llms.md` files, generates indexes |
| `agent-evals/` | Evaluates 10 format axes across 11 task types with 330+ gold standard tasks |

```
Config -> Task Loading -> Variant Setup -> Trial Execution -> Scoring -> Report
                              |                   |
                         (10 axes x           (LLM call per
                          51 variants)     task x variant x rep)
```

## Configuration

Three sources (highest priority wins): **CLI flags > environment variables > config file**.

See `examples/minimal-config.yaml` for a quick start, or `examples/full-config.yaml`
for all options with documentation.

### CLI Reference

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--axis` | int | - | Run all variants for axis N (1-10) |
| `--tasks` | str | - | Filter to specific task types (comma-separated) |
| `--task-id` | str | - | Run a single task by ID (debugging) |
| `--variant` | str | - | Run a single variant by name (debugging) |
| `--model` | str | required | LLM model in provider/name format |
| `--model-config` | str | - | Path to model-specific args YAML |
| `--judge-model` | str | GPT-4o | Override judge model |
| `--limit` | int | - | Max tasks per type (quick iteration) |
| `--repetitions` | int | 10 | Trials per (task, variant) pair |
| `--temperature` | float | 0.3 | LLM sampling temperature |
| `--max-connections` | int | 10 | Concurrent API connections |
| `--max-tasks` | int | 1 | Parallel task evaluation |
| `--dry-run` | flag | false | Estimate tokens and cost without API calls |
| `--max-cost` | float | - | Budget cap in dollars |
| `--no-cache` | flag | false | Force fresh LLM calls (ignore cache) |
| `--output-dir` | str | reports/ | Results directory |
| `--output-format` | str | both | Output format: json, csv, or both |
| `--display` | str | rich | Progress display: rich, plain, or none |
| `--config` | str | ./eval-config.yaml | Path to config file |
| `--continue-on-error` | flag | false | Skip failed trials, report partial results |
| `--verbose / -v` | flag | false | Debug-level logging |
| `--quiet / -q` | flag | false | Warnings and errors only |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key from https://openrouter.ai/keys |

Any config key can also be set as an environment variable with the `AGENT_EVALS_` prefix
using UPPER_SNAKE_CASE. For example, `AGENT_EVALS_REPETITIONS=5` overrides the
`repetitions` config value.

## Key Concepts

See `docs/GLOSSARY.md` for a full glossary. Key terms:

- **Variant**: A concrete index format configuration (e.g., markdown list, YAML, BLUF position)
- **Axis**: An evaluation dimension. Axis 0 holds baseline variants; axes 1-10 each test one format property
- **Trial**: A single (task, variant, repetition) execution scored 0.0-1.0
- **Gold Standard**: The corpus of ~330 annotated YAML task files used for evaluation

## Documentation

- `docs/GLOSSARY.md` - Domain vocabulary
- `docs/EXTENDING.md` - How to add task types, variants, metrics
- `docs/ARCHITECTURE.md` - System design with diagrams
- `docs/TASK_METADATA.md` - Per-task-type metadata field reference
- `planning/DESIGN.md` - Full design specification

Last reviewed: 2026-02-10
