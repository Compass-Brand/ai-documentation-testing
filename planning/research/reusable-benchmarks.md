# Research: Reusable Open-Source Benchmarks & Eval Components

## Key Finding

No existing benchmark directly evaluates documentation index FORMAT on agent performance. Our framework would be the first systematic comparison of index structure, compression, metadata richness, etc. The closest work is the arXiv:2601.20404 paper (presence vs absence of AGENTS.md) and Vercel's eval (AGENTS.md vs Skills).

## Recommended Component Stack

| Need | Best Source | Effort |
|------|-----------|--------|
| Core eval harness | Inspect AI (Task->Solver->Scorer) or DeepEval (pytest-style) | Low |
| Retrieval metrics | RAGAS (context precision/recall), BEIR (nDCG@10) | Low |
| Faithfulness metrics | RAGAS, DeepEval, Braintrust AutoEvals factuality scorer | Low |
| LLM-as-judge prompts | OpenAI Evals templates, LangChain OpenEvals | Very Low |
| Agent trajectory eval | LangChain AgentEvals (trajectory match) | Low |
| Sandboxed execution | SWE-bench Docker harness, Inspect AI Docker sandboxing | Low-Moderate |
| Multi-hop tasks | MultiHop-RAG format, HotpotQA supporting facts, MuSiQue composition | Moderate |
| Robustness testing | PromptBench (4-level perturbation), AbstentionBench (stale data) | Low |
| Test data generation | RAGAS synthetic generation, SWE-smith task generation | Moderate |
| CI/CD integration | Braintrust GitHub Action, Evidently GitHub Action, DeepEval pytest | Low |

## RAG Evaluation Frameworks

### RAGAS (~7k+ stars, Apache 2.0)
- Faithfulness, context precision/recall, answer relevancy metrics
- Noise sensitivity testing
- Synthetic test data generation from docs
- Low modification needed — metrics work out-of-the-box via Python API

### DeepEval (~12.8k stars, Apache 2.0)
- G-Eval: LLM-as-judge with chain-of-thought for custom criteria
- Tool Correctness Metric: evaluates agent tool selection
- 50+ built-in metrics, pytest integration
- Low modification needed — `deepeval test run` maps to eval harness

### TruLens (~3k stars, MIT, maintained by Snowflake)
- OpenTelemetry-based tracing for agent execution
- Ground truth + LLM-as-Judge dual evaluation
- RAG triad metrics with sub-step tracing
- Low-moderate modification — more observability than benchmark

### Braintrust AutoEvals (Apache 2.0)
- Factuality scorer: LLM-as-judge for grounding
- Pre-built judge prompts adapted from OpenAI evals
- CI/CD GitHub Action for PR comparisons
- Low modification needed

### Inspect AI (UK AISI, MIT)
- Dataset -> Task -> Solver -> Scorer pipeline (clean, composable)
- 100+ pre-built evaluations including SWE-bench, coding, reasoning
- Docker sandboxing built-in, VS Code log viewer
- Multi-turn/agent workflow support
- **Best architectural fit** for our eval framework

## Agent Benchmarks

### SWE-bench (~4k+ stars, MIT)
- Docker-based eval harness: containerized execution + test validation
- Oracle Retrieval baselines: perfect retrieval comparison methodology
- SWE-smith: generates unlimited tasks from arbitrary repos
- Moderate-high modification for direct reuse, but infrastructure is battle-tested

### AgentBench (~2.6k stars, ICLR 2024)
- 8-environment eval framework with multi-dimensional scoring
- Reciprocal-average weighting: hard tasks get more weight
- High modification needed — no documentation environment

### MLE-bench (OpenAI, ~1.3k stars)
- 75 Kaggle-competition tasks with automated scoring
- Human baselines via Kaggle leaderboards
- High modification, but methodology is transferable

## Multi-Hop Reasoning

### HotpotQA (CC BY-SA 4.0 data, Apache 2.0 code)
- Multi-hop questions requiring 2+ document reasoning
- Supporting fact annotations (title + sentence ID)
- Comparison and bridge question types
- Moderate adaptation: replace Wikipedia with documentation sections

### MuSiQue (MIT Press TACL)
- Single-hop composition methodology for constructing multi-hop questions
- Anti-shortcut design prevents solving without actual multi-hop reasoning
- Most valuable piece: composition methodology for generating documentation tasks

### MultiHop-RAG (ODC-BY license, COLM 2024)
- 2,556 multi-hop queries with 2-4 document evidence
- Metadata-aware queries (dates, authors, not just content)
- Low-moderate adaptation — data format directly reusable

## Robustness

### PromptBench (Microsoft)
- 4-level perturbation: character, word, sentence, semantic
- Directly applicable to testing index content robustness
- Low adaptation — perturbation functions apply directly

### AbstentionBench (Facebook Research)
- 20 datasets, 35K+ queries across 6 abstention scenarios
- "Stale data" scenario directly applicable
- Abstention recall metric
- Low-moderate adaptation

## Code Generation

### HumanEval/MBPP (MIT/Apache 2.0)
- 164/974 function-level tasks with test cases
- pass@k metric standard
- Low adaptation: add documentation context, compare with different index formats

## LLM-as-Judge

### OpenAI Evals (~17.6k stars, MIT)
- YAML-based eval configs, model-graded infrastructure
- Registry of hundreds of eval configurations as templates
- Low modification

### LangChain AgentEvals
- Trajectory match evaluator: compare actual vs expected file-access patterns
- Strict and LLM-graded modes
- **Almost exactly what we need** for "did the agent navigate correctly?"

## Sources

- RAGAS: https://github.com/vibrantlabsai/ragas
- DeepEval: https://github.com/confident-ai/deepeval
- TruLens: https://github.com/truera/trulens
- Inspect AI: https://github.com/UKGovernmentBEIS/inspect_ai
- SWE-bench: https://github.com/SWE-bench/SWE-bench
- AgentBench: https://github.com/THUDM/AgentBench
- PromptBench: https://github.com/microsoft/promptbench
- AbstentionBench: https://github.com/facebookresearch/AbstentionBench
- OpenAI Evals: https://github.com/openai/evals
- LangChain AgentEvals: https://github.com/langchain-ai/agentevals
- MultiHop-RAG: https://github.com/yixuantt/MultiHop-RAG
- HotpotQA: https://github.com/hotpotqa/hotpot
- BEIR: https://github.com/beir-cellar/beir
- HumanEval: OpenAI (MIT)
- Vercel AGENTS.md eval: https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
- arXiv:2601.20404: "On the Impact of AGENTS.md Files"
