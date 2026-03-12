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

# First-time setup: prepare gold standard datasets
agent-evals --prepare-datasets all --dataset-limit 100

# Run evaluation (uses HF datasets as gold standard)
agent-evals --model openrouter/provider/name

# Run with legacy hand-crafted tasks
agent-evals --source legacy --model openrouter/provider/name

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

### agent-evals CLI reference

#### Quick reference

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--model` | str | (required) | LLM model (`openrouter/provider/name`) |
| `--mode` | str | `taguchi` | `full` or `taguchi` |
| `--limit` | int | none | Max tasks per type (BUG: currently limits total, not per-type) |
| `--repetitions` | int | 10 | Reps per (task, variant) pair |
| `--temperature` | float | 0.3 | LLM sampling temperature |
| `--dry-run` | bool | false | Estimate cost without API calls |
| `--axis` | int | none | Run only axis N (1-12) |
| `--tasks` | str | none | Filter task types (comma-separated) |
| `--task-id` | str | none | Single task by ID (debugging) |
| `--variant` | str | none | Single variant by name (debugging) |
| `--models` | str | none | Multi-model list (taguchi: model becomes a factor) |
| `--pipeline` | str | none | `auto` or `semi` for 3-phase DOE |
| `--top-k` | int | 3 | Top N factors for Phase 3 refinement |
| `--alpha` | float | 0.05 | ANOVA significance threshold |
| `--quality-type` | str | `larger_is_better` | S/N ratio type |
| `--oa-type` | str | auto | Force specific OA (e.g., `L54`, `L121`) |
| `--max-connections` | int | 10 | Concurrent API connections |
| `--max-tasks` | int | 1 | Parallel task evaluation threads |
| `--source` | str | `gold_standard` | Task source: `gold_standard`, dataset name, or comma-list |
| `--dataset-limit` | int | none | Max tasks per dataset source |
| `--prepare-datasets` | str | none | Download+convert without running evals |
| `--list-datasets` | bool | false | Show available datasets and exit |
| `--judge-enabled` | bool | false | Enable LLM-as-judge on sampled trials |
| `--judge-model` | str | `openrouter/openai/gpt-4o-mini` | Judge model |
| `--judge-sample-rate` | int | 20 | 1-in-N trials sent to judge (20 = 5%) |
| `--judge-mode` | str | `routine` | `routine` (single model) or `poll` (panel) |
| `--context-strategy` | str | `full_context` | Context delivery strategy |
| `--strategies` | str | none | Multi-strategy pipeline (comma-separated) |
| `--strategy-reps` | str | none | Per-strategy rep overrides |
| `--budget` | float | none | Total cost cap in dollars |
| `--model-budgets` | str | none | Per-model caps: `model=N.NN,...` |
| `--output-dir` | str | `reports/` | Results directory |
| `--output-format` | str | `both` | `json`, `csv`, or `both` |
| `--display` | str | `rich` | Progress: `rich`, `plain`, `none` |
| `--report` | str | none | `html`, `markdown`, `both`, or `none` |
| `--store-traces` | bool | false | Store prompt/response in observatory DB |
| `--resume` | str | none | Resume crashed run by run_id |
| `--resume-pipeline` | str | none | Resume pipeline by pipeline_id |
| `--continue-on-error` | bool | false | Skip failed trials |
| `--no-cache` | bool | false | Force fresh API calls |
| `--config` | str | `./eval-config.yaml` | Config file path |
| `--dashboard` | bool | false | Enable live dashboard |
| `--model-group` | str | none | Model group name |
| `--sync-interval` | float | 6.0 | Model sync interval (hours) |
| `--verbose` / `-v` | bool | false | Debug-level logging |
| `--quiet` / `-q` | bool | false | Warnings only |

#### Evaluation modes

**Full mode** (`--mode full`): Runs all variant combinations (Cartesian product) against all tasks. Use for small scopes or when you need exhaustive coverage.

**Taguchi mode** (`--mode taguchi`, default): Uses orthogonal array (OA) to test a statistically-designed subset. Current design: 12 factors (axes 1-12) requires L121 OA (121 runs). Each OA row specifies one variant per axis, forming a composite variant. All selected tasks run against each composite.

#### Pipeline phases (--pipeline auto)

1. **Screening**: Full OA run, computes S/N ratios, main effects, ANOVA
2. **Confirmation**: Runs optimal config, validates predicted S/N against prediction interval
3. **Refinement**: Full factorial on top-k factors (others fixed at optimal)

```bash
# Single-phase screening
agent-evals --mode taguchi --model openrouter/provider/name

# Full 3-phase pipeline
agent-evals --mode taguchi --pipeline auto --top-k 3 --model openrouter/provider/name
```

#### Judge (LLM-as-judge)

Judge works in both full and taguchi modes. When enabled, 1-in-N trials get a second evaluation from the judge model. Judge score stored in `trial.metrics["judge_score"]`.

```bash
agent-evals --judge-enabled \
  --judge-model openrouter/stepfun/step-3.5-flash:free \
  --judge-sample-rate 5 \
  --model openrouter/arcee-ai/trinity-large-preview:free
```

#### Context strategies

6 available: `full_context` (default), `system_prompt`, `rag`, `tool_based`, `mcp_native`, `compression`. Strategy sub-parameters (token_budget, chunk_method, etc.) are YAML-only.

```bash
# Single strategy
agent-evals --context-strategy rag --model openrouter/provider/name

# Multi-strategy comparison (runs independent DOE pipeline per strategy)
agent-evals --pipeline auto --strategies "full_context,rag,tool_based"
```

#### Data sources and datasets

9 HF dataset adapters: ambigqa, bigcodebench, code-rag-bench, ds1000, ibm-techqa, multihop-rag, repliqa, swe-bench, wikicontradict.

```bash
# Prepare datasets (no API key needed)
agent-evals --prepare-datasets "ambigqa,ds1000" --dataset-limit 50

# Run from dataset
agent-evals --source ambigqa --dataset-limit 100 --model openrouter/provider/name

# ibm-techqa MUST use --dataset-limit (28K files)
agent-evals --source ibm-techqa --dataset-limit 10 --model openrouter/provider/name
```

#### Key flag interactions

- `--limit` vs `--dataset-limit`: limit caps tasks per type (after loading); dataset-limit caps per dataset source (during loading)
- `--pipeline` requires `--mode taguchi`
- `--strategies` requires `--pipeline`
- `--models` in taguchi mode adds "model" as a Taguchi factor
- `--top-k` and `--alpha` only apply with `--pipeline`
- `--judge-*` flags ignored unless `--judge-enabled` is set
- `--budget` stops evaluation when cost cap reached

#### Subcommands

```bash
# Dashboard (standalone)
agent-evals dashboard --port 8080 --host 0.0.0.0

# Export/import runs
agent-evals export <run_id> -o output.json
agent-evals import bundle.json [--force]
```

#### Config precedence

CLI args > environment variables (`AGENT_EVALS_` prefix) > YAML config file > defaults

#### Trial count formulas

```
Full mode:    trials = n_variants × n_tasks × repetitions
Taguchi mode: trials = OA_rows × n_tasks × repetitions
```

Example: L121, limit 5 (per type), 11 types, 1 rep = 121 × 55 × 1 = 6,655 trials

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
