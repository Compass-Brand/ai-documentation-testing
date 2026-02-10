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
agent-evals run --config examples/minimal-config.yaml

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

Three sources (highest priority wins): CLI flags > environment variables > config file.

See `examples/minimal-config.yaml` for a quick start, or `examples/full-config.yaml`
for all options with documentation.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key from https://openrouter.ai/keys |

## Key Concepts

See `docs/GLOSSARY.md` for a full glossary. Key terms:

- **Variant**: A concrete index format configuration (e.g., markdown list, YAML, BLUF position)
- **Axis**: An evaluation dimension (1-10) testing one format variable (scale, metadata, format, etc.)
- **Trial**: A single (task, variant, repetition) execution scored 0.0-1.0
- **Gold Standard**: The corpus of ~330 annotated YAML task files used for evaluation

## Documentation

- `docs/GLOSSARY.md` - Domain vocabulary
- `docs/EXTENDING.md` - How to add task types, variants, metrics
- `docs/ARCHITECTURE.md` - System design with diagrams
- `docs/TASK_METADATA.md` - Per-task-type metadata field reference
- `planning/DESIGN.md` - Full design specification
