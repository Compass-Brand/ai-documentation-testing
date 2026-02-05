# Plan: Better Documentation Search — v2 Overhaul

## Summary

Evolve the current flat docs-index generator into an **opinionated, multi-tier documentation system** with an **evaluation framework** that empirically determines the best format/structure for AI agent consumption. Three major workstreams: (A) multi-tier generator, (B) evaluation framework, (C) user experience improvements.

---

## Workstream A: Multi-Tier Generator

### A1. Tiered Output Format

Redesign the generator's output so the root AGENTS.md/CLAUDE.md is very short (~40-60 lines, <1K tokens) with distinct sections:

**Section layout (position-aware ordering based on "lost in the middle" research):**

```
[TOP — highest attention]
  IMPORTANT retrieval instruction
  Required section → table of must-read docs with token estimates + summaries
  Commands section → key project commands in fenced code block

[MIDDLE — lower attention]
  Reference sections → compressed pointers organized by topic
  Each section has a micro-summary in the header so agents can skip irrelevant ones

[BOTTOM — high attention]
  Boundaries section → always/ask-first/never rules
  IMPORTANT retrieval instruction (repeated)
```

**Required section uses a table format:**
```markdown
## Required [Read these docs at the start of every session]

| Doc | Path | ~Tokens | Summary |
|-----|------|---------|---------|
| Architecture | required/architecture.md | ~480 | System design, module boundaries |
| Setup | required/setup.md | ~320 | Local dev, env vars, dependencies |
```

**Reference sections each have independent markers for per-section updates:**
```markdown
## API [Auth, database, routes — read when modifying endpoints]

<!-- API-DOCS-START -->
api/auth:{login.md,oauth.md,tokens.md}
api/routes:{middleware.md,validation.md}
<!-- API-DOCS-END -->
```

**Files to modify:**
- `scripts/generate_docs_index.py` — Add new dataclasses (`RequiredDoc`, `ReferenceSection`, `CommandEntry`, `Boundaries`, `TieredConfig`), new `format_tiered()` formatter, `scan_tiered_sources()` scanner, token estimation utility

### A2. Recommended Directory Structure (Opinionated Defaults)

Define a recommended layout that the tool produces by default, but allow configuration for existing projects:

```
project-root/
  AGENTS.md                    # Root file (~60 lines max)
  .agent-docs/                 # Agent-consumed documentation
    required/                  # Tier 1: must-read at session start
      architecture.md
      setup.md
      conventions.md
    reference/                 # Tier 2: on-demand by topic
      api/
      testing/
      deployment/
```

The generator enforces this layout when creating new configs but adapts to arbitrary existing structures via config mapping.

### A3. Multiple Output Formats

Support three output format options via `--format` flag:
- `flat` — Current pipe-delimited format (default, backward compatible)
- `tiered` — New multi-tier Markdown with required/reference/boundaries sections
- `yaml-index` — YAML-based index (27% more token-efficient per research)

The eval framework (Workstream B) will determine which format performs best. All three share the same scanning/config infrastructure.

### A4. Token Cost Estimation

Add token estimation to the generator:
- Estimate tokens per doc file (~4 chars/token heuristic, or `tiktoken` if available)
- Display in the Required section table
- Print total token budget in stats output
- Warn if index exceeds recommended 5-10K token budget

### A5. CI Validation Mode

Add `--validate` flag that:
- Compares generated index against actual docs on disk/GitHub
- Reports missing files, extra files, stale entries
- Returns non-zero exit code on drift
- Suitable for pre-commit hooks and CI pipelines

### A6. Multi-Index Support

Support generating multiple independent indexes from one config (e.g., one per package in a monorepo). Each index gets its own marker pair and can be injected independently.

---

## Workstream B: Evaluation Framework

### B1. Framework Architecture

Create `evals/` directory with a plugin-based variant system:

```
better-documentation-search/
  evals/
    conftest.py                # pytest fixtures
    runner.py                  # Main harness: load variants, run evals, score
    scoring.py                 # Score computation, aggregation, statistics

    variants/                  # Format variant plugins (auto-discovered)
      base.py                  # Abstract IndexVariant base class
      registry.py              # Auto-discovery via @register decorator
      pipe_delimited.py        # Current format (baseline)
      yaml_index.py            # YAML variants
      markdown_tiered.py       # Markdown tiered variants
      toon_index.py            # TOON format variants

    tasks/                     # Eval task definitions
      base.py                  # Abstract EvalTask base class
      retrieval.py             # "Which file answers this question?"
      fact_extraction.py       # "What does this API do?"
      code_generation.py       # "Write code using this API"
      loader.py                # Load tasks from YAML

    task_data/                 # YAML test case definitions
      retrieval_tasks.yaml
      fact_extraction_tasks.yaml
      code_generation_tasks.yaml

    fixtures/                  # Static test data
      sample_docs/             # Real doc files for code gen tasks
      doc_tree.json            # Canonical directory structure

    llm/                       # LLM interaction
      client.py                # API wrapper (Anthropic + OpenAI)
      cache.py                 # Disk-backed response cache
      token_counter.py         # Token counting utilities

    reports/                   # Output directory
```

### B2. Variant System

Each variant is a self-contained class implementing `render(doc_tree, summaries, priorities) -> str`. New variants are added by creating a single file — no changes to runner or config.

**Test axes (each holding other variables constant):**

| Axis | Variants | What It Tests |
|------|----------|---------------|
| Format family | pipe-delimited, yaml, markdown, toon | Which serialization format LLMs comprehend best |
| Structure | flat, 2-tier, 3-tier progressive | Whether tiering helps vs flat |
| Metadata level | bare filenames, micro-summaries, full annotations | Whether extra metadata justifies extra tokens |
| Position strategy | natural, BLUF, importance-at-edges, random | Whether ordering matters |
| Compression | index-only, index+summaries, full docs inlined | Where the sweet spot is |

~18 total variants across all axes.

### B3. Three Task Types

**Retrieval** (weight: 0.40) — Given a coding question and an index, identify the correct doc file(s). Scored by F1 (precision + recall). Tests the primary failure mode (56% of agents never invoke retrieval).

**Fact extraction** (weight: 0.25) — Given index + doc content, answer a factual API question. Scored by keyword matching against expected answers + aliases.

**Code generation** (weight: 0.35) — Given index + doc content, produce a code snippet. Scored by required regex patterns present + forbidden anti-patterns absent.

### B4. Token Efficiency Metrics

Per variant:
- **Index token count** — Raw size
- **Information density** — Composite score / index tokens
- **Efficiency ratio** — Composite score / (tokens / baseline tokens)
- **Marginal token cost** — Extra tokens vs extra score compared to baseline

### B5. Statistical Rigor

- Each task run N times per variant (default N=3, configurable)
- Mean + standard deviation per variant per task type
- Pairwise variant comparisons using Wilcoxon signed-rank test
- Console summary table + JSON results file for downstream analysis

### B6. Response Caching

Disk-backed cache keyed on `(model, temperature, prompt_hash)`. At temperature 0.0, reruns use cached responses. Iterate on scoring logic without re-running LLM calls. ~2M tokens total for a full matrix run (~$6 with Sonnet).

### B7. Evaluation Tiers

Three levels of evaluation, cheapest to most expensive:

1. **Static analysis** (zero cost) — Token counts, structural metrics, format overhead ratios
2. **Targeted LLM probes** (low cost) — Single-turn retrieval/fact/code tasks (~972 calls)
3. **Mini agent simulation** (medium cost, optional) — Two-turn: LLM reads index → decides what to fetch → receives doc → produces code. Tests full pipeline without a real project.

Run tiers 1+2 during iteration. Tier 3 for final validation of top candidates.

---

## Workstream C: User Experience

### C1. Interactive Config Wizard (`--init`)

An `npm init`-style interactive CLI that:
1. Asks for project name, framework
2. Asks where docs live (local path and/or GitHub repo)
3. Asks which sections are required vs reference
4. Asks for key project commands
5. Asks for boundary rules
6. Generates a complete `sources.yaml` config

### C2. Auto-Detect Mode (`--auto-detect`)

For existing projects:
1. Scan the project directory for common doc locations (`docs/`, `documentation/`, `wiki/`, `README.md`, etc.)
2. Detect documentation structure and frameworks
3. Heuristically assign directories to required vs reference tiers
4. Propose a config that the user can review and edit
5. Generate placeholder micro-summaries from directory/file names

### C3. Test Suite

Add `tests/` directory with pytest tests covering:
- Config loading (YAML, JSON, TOML)
- Local directory scanning
- GitHub API response parsing
- All three output formatters (flat, tiered, yaml-index)
- File injection/replacement logic
- Token estimation
- Validation mode
- Config wizard output

---

## Implementation Order

| Phase | What | Depends On |
|-------|------|------------|
| 1 | Test suite for existing functionality | Nothing |
| 2 | Multi-tier dataclasses + config loading | Phase 1 |
| 3 | Tiered formatter + YAML formatter | Phase 2 |
| 4 | Token estimation + position-aware ordering | Phase 2 |
| 5 | CI validation mode | Phase 2 |
| 6 | Eval framework scaffolding (variants, tasks, runner) | Nothing (parallel with 1-5) |
| 7 | Eval variant implementations + task data | Phase 6 |
| 8 | Run evaluations, analyze results | Phase 7 |
| 9 | Refine formats based on eval results | Phase 8 |
| 10 | Config wizard + auto-detect | Phase 2 |
| 11 | Multi-index support | Phase 3 |

Phases 1-5 and 6-7 can proceed in parallel.

---

## Files to Create/Modify

**Modify:**
- `scripts/generate_docs_index.py` — New dataclasses, formatters, CLI flags, token estimation, validation mode, wizard, auto-detect
- `scripts/sources.example.yaml` — Extend with tiered config example
- `scripts/output.example.md` — Add tiered output example
- `README.md` — Document new features

**Create:**
- `tests/` — Full test suite
- `evals/` — Entire evaluation framework (structure above)
- `evals/task_data/*.yaml` — Test case definitions
- `evals/fixtures/` — Sample docs and canonical doc tree

**Delete:**
- Root-level test artifacts: `test_ver.py`, `test_output.txt`, `py_stdout.txt`, `py_stderr.txt`

---

## Verification

1. **Existing functionality preserved**: Run `python generate_docs_index.py --local ./docs` and confirm flat output matches current behavior
2. **Tiered output**: Run with `--format tiered` and a tiered config, verify output matches the template structure with correct sections, token estimates, and position ordering
3. **YAML output**: Run with `--format yaml-index`, verify valid YAML that contains the same logical content
4. **Validation mode**: Intentionally remove a doc file, run `--validate`, confirm non-zero exit code and error report
5. **Config wizard**: Run `--init`, walk through prompts, verify generated YAML is valid and complete
6. **Auto-detect**: Run `--auto-detect` against a project with docs, verify proposed config is reasonable
7. **Test suite**: `pytest tests/ -v` — all pass
8. **Eval framework**: `python -m evals.runner --model claude-sonnet-4-20250514 --reps 3` — runs full matrix, produces comparison table and JSON results
9. **Token budgets**: Verify tiered output stays under 1K tokens for root file, under 10K for full index
