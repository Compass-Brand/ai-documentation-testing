# Research: Datasets for Eval Framework

## Strategy

Our eval framework needs 330+ tasks across 11 task types. We use a mix of adapted public datasets and synthetic fixtures generated from documentation corpora. No existing dataset tests documentation index FORMAT, so all public datasets need adaptation from their original domain (Wikipedia, news, general QA) to documentation contexts.

## Dataset Recommendations by Task Type

### Task 1: Retrieval (0.15)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **CodeRAG-Bench lib-docs** | `code-rag-bench/library-documentation` | 10K-100K docs | CC-BY-SA-4.0 | Low |
| **IBM TechQA** | `PrimeQA/TechQA` | 600 train + 310 dev + 490 test | Apache-2.0 | Low |
| **NVIDIA TechQA-RAG-Eval** | `nvidia/TechQA-RAG-Eval` | <1K | Apache-2.0 | Low |
| DocPrompting | GitHub only | ~8K (Bash) + ~2K (Python) | MIT | Low |
| BEIR/SciFact | `BeIR/scifact` | ~5K docs, 1.1K queries | CC-BY-SA-4.0 | Moderate |

**Primary pick:** CodeRAG-Bench library-documentation + DS-1000/ODEX ground-truth annotations. Almost direct fit -- real Python library docs with query-to-document mappings.

**Secondary:** IBM TechQA -- each question comes with 50 candidate technical docs and a relevance label.

### Task 2: Fact Extraction (0.15)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **IBM TechQA** | `PrimeQA/TechQA` | ~1.4K QA pairs | Apache-2.0 | Low |
| **RAGBench (TechQA/EManual)** | `galileo-ai/ragbench` | ~100K total | CC-BY-4.0 | Low-Moderate |
| **Keboola Dev Docs QA** | `Keboola/Developer-Documentation-QA` | 1K-10K | Unspecified | Low |
| NVIDIA TechQA-RAG-Eval | `nvidia/TechQA-RAG-Eval` | <1K | Apache-2.0 | Low |

**Primary pick:** IBM TechQA -- real technical questions with extractive answer spans from technical documents. Covers both retrieval and fact extraction.

**Secondary:** RAGBench TechQA/EManual subsets -- 100K RAG examples with questions, contexts, and ground-truth answers.

### Task 3: Code Generation (0.15)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **CodeRAG-Bench/DS-1000** | `code-rag-bench/ds1000` | 1,000 | CC-BY-SA-4.0 | Low |
| **Long Code Arena** | `JetBrains-Research/lca-library-based-code-generation` | 150 | Apache-2.0 | Low |
| **Gorilla APIBench** | `gorilla-llm/APIBench` | 16,450 | Apache-2.0 | Low |
| DS-1000 | `xlangai/DS-1000` | 1,000 | CC-BY-SA-4.0 | Low |
| BigCodeBench | `bigcode/bigcodebench` | 1,140 | Apache-2.0 | Moderate |
| ODEX | `neulab/odex` | 945 | CC-BY-SA-4.0 | Moderate |

**Primary pick:** CodeRAG-Bench/DS-1000 -- already has ground-truth library documentation annotations. Tasks span 7 Python data science libraries.

**Secondary:** Gorilla APIBench -- 16,450 (doc, query, API call) triples with hallucination detection via AST matching.

### Task 4: End-to-End Agentic (0.12)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **SWE-bench Verified** | `princeton-nlp/SWE-bench_Verified` | 500 | MIT (code)[^1] | Moderate |
| SWE-rebench | `nebius/SWE-rebench` | 10K+ | CC-BY-4.0 | Moderate |
| SWE-bench Pro | `ScaleAI/SWE-bench_Pro` | ~500 | -- | Moderate |
| ACE-Bench | not on HF yet | 212 | -- | Moderate |
| ABC-Bench | not on HF yet | 224 (8 languages) | -- | Moderate |

**Primary pick:** SWE-bench Verified -- 500 human-validated real-world tasks. Well-established evaluation infrastructure. Add documentation indexes as an available tool alongside codebase browsing.

### Task 5: Multi-Hop Reasoning (0.10)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **MultiHop-RAG** | `yixuantt/MultiHopRAG` | 2,556 queries | ODC-BY | Low |
| **MuSiQue** | `dgslibisey/MuSiQue` | ~25K | CC-BY-4.0 | Moderate |
| HotpotQA | `hotpotqa/hotpot_qa` | ~113K | CC-BY-SA-4.0 | Moderate |
| 2WikiMultiHopQA | `xanhho/2WikiMultihopQA` | 100K+ | Apache-2.0 | Moderate |

**Primary pick:** MultiHop-RAG -- built for RAG evaluation, metadata-aware queries, evidence across 2-4 docs. Lowest adaptation effort.

**Secondary:** MuSiQue -- variable hop count (2/3/4), decomposed sub-questions, built-in unanswerable variants.

### Task 6: Negative / Unanswerable (0.08)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **RepLiQA** | `ServiceNow/repliqa` | 10K+ (20% unanswerable) | CC-BY-4.0 | Low |
| **SQuAD 2.0** | `rajpurkar/squad_v2` | 150K (50K unanswerable) | CC-BY-SA-4.0 | Moderate |
| AbstentionBench | `facebook/AbstentionBench` | 35K+ | CC-BY-NC-4.0 | Moderate-High |
| Adversarial QA | `UCLNLP/adversarial_qa` | 36K | CC-BY-SA-4.0 | Moderate |

**Primary pick:** RepLiQA -- synthetic docs prevent contamination, 20% unanswerable, document-centric design, permissive CC-BY-4.0 license.

**Secondary:** SQuAD 2.0 -- massive scale, adversarial unanswerable questions, industry-standard.

### Task 7: Compositional Code Generation (0.07)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **BigCodeBench** | `bigcode/bigcodebench` | 1,140 | Apache-2.0 | Moderate |
| ClassEval | `FudanSELab/ClassEval` | 100 classes, 412 methods | MIT | Moderate |
| CrossCodeEval | `Vincentvmt/CrossCodeEval` | 10K+ | Apache-2.0 | Moderate |

**Primary pick:** BigCodeBench -- tasks require composing functions from 139 libraries. Filter for multi-API tasks and pair with library documentation.

### Task 8: Robustness / Perturbation (0.06)

Use **generator tools** rather than static datasets. Apply perturbations to clean queries from other task types.

| Tool | Source | License | Level | Status |
|------|--------|---------|-------|--------|
| **PromptBench** | `pip install promptbench` | MIT | Character/Word/Sentence/Semantic | Active (Microsoft) |
| **TextAttack** | `pip install textattack` (pin v0.3.10) | MIT | 16+ attack recipes + Augmenter | Last release Mar 2024 |
| PromptCraft | `pip install promptcraft` | MIT | Character/Word/Sentence + style | Backup option |

**Removed:** nlpaug (last release July 2022, abandoned). Use TextAttack's `augmentation.Augmenter` module as replacement.

**Validation reference:** NoiseQA (GitHub: noiseQA/NoiseQA) -- SQuAD subset with keyboard, ASR, and MT noise variants.

**Pre-perturbed benchmark:** RUPBench -- 365K perturbed samples, 9 perturbation types, 15 source datasets.

### Task 9: Disambiguation (0.05)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **AmbigQA** | `sewon/ambig_qa` | 14,042 | CC-BY-SA-3.0 | Moderate |
| ASQA | `din0s/asqa` | 1K-10K | Apache-2.0 | Moderate |
| CondAmbigQA | `Apocalypse-AGI-DAO/CondAmbigQA` | 200-2K (gated) | MIT | Low-Moderate |

**Primary pick:** AmbigQA -- largest ambiguity-annotated dataset, multiple interpretation annotations per question.

**Framework model:** CondAmbigQA -- adopt its condition-based disambiguation schema (conditions like OS, version, module resolve ambiguity).

### Task 10: Conflicting Information (0.04)

| Dataset | HF ID | Size | License | Mod. Level |
|---------|-------|------|---------|------------|
| **WikiContradict** | `ibm-research/Wikipedia_contradict_benchmark` | 253 | MIT | Low |
| ConflictBank (QA) | `Warrieryes/CB_qa` | 553K | See paper | Moderate |
| ConflictBank (claims) | `Warrieryes/CB_claim_evidence` | 7.45M | See paper | Moderate |

**Primary pick:** WikiContradict -- small but precise, MIT licensed, tests conflict identification directly. Augment with synthetic documentation version conflicts.

**Scale source:** ConflictBank temporal conflict subset -- maps to documentation version scenarios.

### Task 11: Efficiency-Constrained (0.03)

No prebuilt dataset. Use methodology from:
- **Reasoning in Token Economies** (EMNLP 2024) -- budget-aware evaluation framework
- **OckBench** -- Tokens/Accuracy metric
- **EffiReason-Bench E3-Score** -- smooth efficiency metric

Apply token budget constraints to tasks from other types (retrieval, fact extraction, code generation).

## Cross-Cutting RAG Evaluation Resources

| Resource | HF ID / Source | Size | License | Use |
|----------|---------------|------|---------|-----|
| **RAGBench** | `galileo-ai/ragbench` | ~100K | CC-BY-4.0 | Multi-task RAG eval, TechQA/EManual subsets |
| **RAGAS** | `pip install ragas` | Generator | Apache-2.0 | Synthetic test data from docs, faithfulness metric |
| **ARES** | GitHub: stanford-futuredata/ARES | Framework | MIT | Automated RAG evaluation with few human annotations |
| RGB | arXiv:2309.01431 | 4 testbeds | Research | Noise robustness + negative rejection |
| CRAG | GitHub: facebookresearch/CRAG | 4,409 QA | CC-BY-NC-4.0 | 8 question categories, mock APIs |

## Licensing Summary

All primary picks use permissive licenses (Apache-2.0, CC-BY-4.0, CC-BY-SA-4.0, MIT, ODC-BY). AbstentionBench (CC-BY-NC-4.0) restricts commercial use -- use for methodology reference only.

## Synthetic Data Generation Strategy

For tasks where no public dataset directly fits (especially documentation-specific scenarios), use:
1. **RAGAS synthetic generator** -- point at documentation corpus, generates multi-hop queries automatically
2. **RAG-ConfusionQA methodology** -- generate confusing/ambiguous questions from docs (~$50 via GPT-4o-mini)
3. **PromptBench/TextAttack** -- perturb clean queries to create robustness variants
4. **MuSiQue composition method** -- compose single-hop questions into multi-hop chains

---

[^1]: SWE-bench codebase is MIT-licensed; dataset content is sourced from open-source GitHub repos with their own licenses. No explicit dataset-level license declared on HF. Also available at `SWE-bench/SWE-bench_Verified`.
