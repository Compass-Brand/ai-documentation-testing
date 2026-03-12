# Gold Standard Annotation Protocol

## 1. Overview

### Purpose

The gold standard corpus serves two functions:

1. **Calibrate the LLM-as-judge scorer.** Human-annotated scores establish ground truth against which the LLM judge (GPT-4o via OpenRouter, or PoLL panel for final comparison) is measured. Calibration target: Cohen's kappa >= 0.70, Spearman rho >= 0.80 between judge output and gold standard.
2. **Validate deterministic scorers.** Where deterministic metrics (F-beta, keyword match, regex patterns) serve as primary or secondary scorers, gold standard annotations verify their alignment with human judgment. When LLM-judge and deterministic scorer disagree, the gold standard breaks ties.

### Corpus Size

- **30-50 annotated examples per task type**
- **11 task types** = **330-550 total annotated examples**
- Minimum 150 examples for production judge validation (per DESIGN.md calibration targets)
- 60 examples allocated to Phase 1 (rubric iteration) before production annotation begins

### Difficulty Distribution

Each task type's examples follow this distribution:

| Difficulty | Proportion | Description |
|------------|------------|-------------|
| Easy       | 30%        | Straightforward queries with unambiguous answers in a single source |
| Medium     | 40%        | Requires moderate reasoning, some cross-referencing, or partial matches |
| Hard       | 20%        | Requires deep reasoning, multiple sources, or nuanced interpretation |
| Edge case  | 10%        | Adversarial inputs, boundary conditions, malformed queries, or degenerate cases |

For a task type with 40 examples: 12 easy, 16 medium, 8 hard, 4 edge cases.


## 2. Annotator Instructions

### Scoring Scale

Score each LLM response on a continuous **0.0-1.0 scale** with 0.1 increments.

| Score Range | Meaning |
|-------------|---------|
| 0.0         | Completely wrong, no useful content, or harmful fabrication |
| 0.1-0.3     | Mostly wrong with minor correct elements |
| 0.4-0.6     | Partially correct; key information present but incomplete or contains errors |
| 0.7-0.8     | Largely correct with minor omissions or imprecisions |
| 0.9         | Correct and complete with trivial imperfections |
| 1.0         | Perfect response meeting all rubric criteria |

### Required Output Per Example

For each annotated example, record:

```yaml
example_id: "retrieval_024"
task_type: "retrieval"
difficulty: "medium"
annotator_id: "ann_01"
score: 0.8
rationale: >
  Found 4 of 5 expected files. Missed utils/config.py which contains
  relevant configuration defaults. All returned files were relevant
  (no false positives).
timestamp: "2026-02-06T14:30:00Z"
```

### General Rules

1. **Score independently.** Do not discuss scores with other annotators before submitting your initial annotation. Discussion occurs only during adjudication.
2. **Grade outcomes, not paths.** Evaluate what the agent produced, not its reasoning steps or tool-call sequence. Two agents producing identical outputs receive identical scores.
3. **Write a rationale for every score.** The rationale must reference specific rubric criteria. "Looks good" is insufficient; "Correctly identified all 3 API endpoints but missed the deprecation note for v2" is sufficient.
4. **Use the full scale.** Avoid clustering all scores at 0.5-0.8. Easy examples should score near 1.0 or 0.0; use the extremes when warranted.
5. **Flag ambiguous examples.** If the expected answer or rubric criteria are unclear, flag the example with `ambiguous: true` and describe the ambiguity in the rationale. Flagged examples are reviewed during rubric iteration.
6. **Do not penalize verbosity or brevity** unless the task-specific rubric explicitly includes a conciseness criterion. Score correctness and completeness first.


## 3. Task-Specific Rubrics

Each rubric maps the 0.0-1.0 scale to task-specific criteria. Annotators should use these rubrics as the primary reference when assigning scores.

---

### 3.1 Retrieval (weight: 0.15)

**What is scored:** Whether the correct files/documents are identified in response to a query.

**Primary metric context:** F-beta (beta=2) weights recall over precision. Missing a needed document costs more than including an extra.

| Score | Criteria |
|-------|----------|
| 1.0   | All expected files found, no false positives |
| 0.8   | All expected files found, 1-2 irrelevant files included |
| 0.6   | Most expected files found (>= 75%), minor false positives |
| 0.4   | Some expected files found (50-74%), or significant false positives |
| 0.2   | Few expected files found (< 50%), mostly irrelevant results |
| 0.0   | No expected files found, or completely wrong file set |

**Rubric notes:**
- Recall matters more than precision. A response that finds all correct files plus 2 extras scores higher than one that finds 3 of 5 correct files with no extras.
- Partial credit for files in the correct directory but wrong specific file.
- Rank order does not matter unless the task explicitly requests ranked results.

---

### 3.2 Fact Extraction (weight: 0.15)

**What is scored:** Factual accuracy of answers extracted from documentation.

**Primary metric context:** LLM-as-judge with structured rubric (correctness 0.6, completeness 0.3, conciseness 0.1).

| Score | Criteria |
|-------|----------|
| 1.0   | Exact correct answer with full detail and appropriate nuance |
| 0.8   | Correct answer, minor detail missing or slightly imprecise wording |
| 0.6   | Core fact correct but missing important qualifications or context |
| 0.4   | Partially correct; contains the right idea but also includes errors |
| 0.2   | Mostly incorrect with a minor correct element |
| 0.0   | Completely wrong answer or fabricated information |

**Rubric notes:**
- Factual correctness dominates. A concise wrong answer scores lower than a verbose correct one.
- Numeric answers: exact match = 1.0; within 5% = 0.8; within 20% = 0.5; otherwise 0.0-0.2.
- For answers with multiple facts, score each fact and average. Document which facts were correct/incorrect in the rationale.

---

### 3.3 Code Generation (weight: 0.15)

**What is scored:** Correctness of generated code, including API usage, patterns, and absence of bugs.

**Primary metric context:** Deterministic test suite (regex + forbidden anti-patterns) as primary. LLM-as-judge as secondary for API usage and conventions.

| Score | Criteria |
|-------|----------|
| 1.0   | Working code, correct API usage, follows conventions, handles errors |
| 0.8   | Working code with correct approach, minor style issues or missing edge-case handling |
| 0.6   | Correct approach and mostly working, but contains 1-2 bugs that would cause failures |
| 0.4   | Right general approach but significant bugs or wrong API usage |
| 0.2   | Wrong approach but demonstrates some understanding of the domain |
| 0.0   | Completely wrong approach, non-functional code, or uses fabricated APIs |

**Rubric notes:**
- "Working code" means it would execute without errors given appropriate inputs and dependencies.
- Using deprecated APIs scores no higher than 0.6 unless the task specifically targets legacy code.
- Forbidden anti-patterns (as defined per task) reduce the score by 0.2-0.4 depending on severity.
- Code that passes all deterministic tests but uses poor patterns: cap at 0.8.

---

### 3.4 Agentic (weight: 0.12)

**What is scored:** Correct tool usage, file understanding, and problem resolution in an end-to-end agent scenario.

**Primary metric context:** Composite of retrieval invocation, file selection, and output correctness. Captures the skill-non-invocation failure mode.

| Score | Criteria |
|-------|----------|
| 1.0   | Correct tool invocations, correct file selection, correct final output |
| 0.8   | Correct final output with minor inefficiency in tool usage (extra calls, suboptimal order) |
| 0.6   | Correct file selection and reasonable output, but missed a tool call or included an unnecessary one |
| 0.4   | Partially correct output; some correct tool usage but missed key retrieval steps |
| 0.2   | Wrong output despite some correct individual tool calls |
| 0.0   | Failed to invoke relevant tools, wrong files, wrong output |

**Rubric notes:**
- Score the outcome first, then adjust for tool usage quality. An agent that gets the right answer through an inefficient path still scores >= 0.7.
- Failure to invoke a tool when needed (skill non-invocation) is a significant penalty: -0.3 minimum.
- Record the tool-call sequence in the rationale for later trajectory analysis.

---

### 3.5 Multi-Hop Reasoning (weight: 0.10)

**What is scored:** Correctly connecting information from 2-3 documents to produce a synthesized answer.

| Score | Criteria |
|-------|----------|
| 1.0   | All hops correctly identified and synthesized into a complete answer |
| 0.8   | All hops identified, synthesis mostly correct with minor gap |
| 0.6   | Most hops identified (missed one connection), partial synthesis |
| 0.4   | Some relevant information found but failed to connect across documents |
| 0.2   | Only single-document information used despite multi-hop requirement |
| 0.0   | Wrong answer or no evidence of cross-document reasoning |

**Rubric notes:**
- Each "hop" is a distinct piece of information from a different source. Count the expected hops and track which were completed.
- A correct final answer that skips an intermediate hop (lucky guess) scores no higher than 0.5. The reasoning chain matters for this task type.
- Accuracy drops 25-30 points vs single-hop benchmarks (HotpotQA, MuSiQue data). Calibrate difficulty expectations accordingly.

---

### 3.6 Negative / Unanswerable (weight: 0.08)

**What is scored:** Correctly abstaining when the information is not available in the provided documentation.

| Score | Criteria |
|-------|----------|
| 1.0   | Explicit, clear abstention (e.g., "This information is not in the available documentation") |
| 0.8   | Abstention with minor hedging but still clearly declines to answer |
| 0.5   | Expresses uncertainty but still provides a speculative answer |
| 0.2   | Provides a confident answer with fabricated information |
| 0.0   | Provides a fully fabricated answer with no indication of uncertainty |

**Rubric notes:**
- This is a binary-leaning task: the model either abstains (correct) or fabricates (incorrect). The scale captures degrees of hedging.
- Reasoning-tuned models show 24% worse abstention rates (AbstentionBench). Annotators should not be lenient on partial fabrications.
- A response that says "I'm not sure but..." and then gives the wrong answer scores 0.2-0.3, not 0.5.
- A response that correctly identifies which parts are answerable vs. not scores up to 0.8 even if it provides partial information for the answerable parts.

---

### 3.7 Compositional (weight: 0.07)

**What is scored:** Answering all sub-parts of a multi-part question correctly.

| Score | Criteria |
|-------|----------|
| 1.0   | All sub-parts answered correctly and completely |
| 0.8   | All sub-parts addressed, one has a minor error |
| 0.6   | Most sub-parts correct, one sub-part wrong or missing |
| 0.4   | About half of sub-parts correct |
| 0.2   | Only one sub-part correct, others wrong or missing |
| 0.0   | No sub-parts answered correctly, or question misunderstood entirely |

**Rubric notes:**
- Score = (number of correct sub-parts / total sub-parts), then adjust for partial correctness within sub-parts.
- A sub-part that is partially correct counts as 0.5 of a sub-part.
- If the response addresses all sub-parts but in a disorganized way, do not penalize structure -- only penalize missing or incorrect content.

---

### 3.8 Robustness (weight: 0.06)

**What is scored:** Giving the same correct answer despite question perturbation (rephrasing, typos, different terminology).

| Score | Criteria |
|-------|----------|
| 1.0   | Correct answer identical (or semantically equivalent) to baseline, unaffected by perturbation |
| 0.8   | Correct answer with minor variation in detail level compared to baseline |
| 0.5   | Answer changed in a meaningful way but is still partially correct |
| 0.2   | Answer significantly degraded by perturbation; was correct on baseline but now mostly wrong |
| 0.0   | Completely different (wrong) answer compared to correct baseline |

**Rubric notes:**
- Robustness tasks always have a paired baseline (the unperturbed question). Annotators must score the perturbed response relative to the expected correct answer, not relative to the baseline response.
- Minor wording differences in correct answers are acceptable (score 0.8-1.0).
- If the baseline itself was incorrect, flag the example as `baseline_error: true`.

---

### 3.9 Disambiguation (weight: 0.05)

**What is scored:** Identifying the correct interpretation of an ambiguous query.

| Score | Criteria |
|-------|----------|
| 1.0   | Correctly identifies the intended interpretation and provides the right answer |
| 0.8   | Identifies the intended interpretation, asks a reasonable clarifying question, then answers correctly |
| 0.6   | Provides answers for multiple interpretations including the correct one, but does not identify which is intended |
| 0.4   | Answers the wrong interpretation but acknowledges ambiguity |
| 0.2   | Answers the wrong interpretation without acknowledging ambiguity |
| 0.0   | Misunderstands the query entirely |

**Rubric notes:**
- Asking for clarification is acceptable and should not be heavily penalized if the question is genuinely ambiguous.
- If the task has a single clearly intended interpretation (based on context), failing to select it is penalized more than in genuinely ambiguous cases.
- Document which interpretation the annotator considers correct and why.

---

### 3.10 Conflicting Information (weight: 0.04)

**What is scored:** Resolving contradictions between sources using authority, recency, or explicit conflict acknowledgment.

| Score | Criteria |
|-------|----------|
| 1.0   | Identifies the conflict, selects the correct resolution (by authority/recency), explains reasoning |
| 0.8   | Selects the correct resolution without explicitly identifying the conflict |
| 0.6   | Identifies the conflict but selects the wrong resolution or fails to resolve |
| 0.4   | Provides one source's answer without acknowledging the conflict exists |
| 0.2   | Merges conflicting information into an internally inconsistent answer |
| 0.0   | Provides the wrong source's answer confidently, no awareness of conflict |

**Rubric notes:**
- Each conflicting-info task must specify the expected resolution strategy (authority, recency, or explicit flag). Annotators use this to judge correctness.
- Acknowledging a conflict without resolving it scores 0.5-0.6 depending on the quality of the acknowledgment.
- Merging contradictory facts into a single statement (creating a novel falsehood) is worse than picking the wrong source.

---

### 3.11 Efficiency (weight: 0.03)

**What is scored:** Correctness within token budget constraints.

| Score | Criteria |
|-------|----------|
| 1.0   | Correct answer within the specified token budget |
| 0.8   | Correct answer, slightly over budget (within 10% overshoot) |
| 0.5   | Correct answer but significantly over budget (> 10% overshoot) |
| 0.3   | Within budget but partially incorrect |
| 0.0   | Wrong answer regardless of budget compliance, or massively over budget (> 2x) |

**Rubric notes:**
- Correctness is weighted above budget compliance. A correct answer at 120% of budget scores higher than a wrong answer at 80% of budget.
- Token count is measured by the tokenizer specified in the task (default: `cl100k_base`).
- For tasks with no explicit budget, this rubric does not apply. Flag such tasks as `no_budget: true`.


## 3.12 Canary & Sentinel Tasks

### Naming Convention

Canary and sentinel tasks use a `canary_NNN` or `sentinel_NNN` task_id prefix regardless of which task type directory they reside in. This is intentional: their `type` field reflects the actual task type being tested (e.g., `factual_retrieval`, `negative`), while the `task_id` prefix signals their QA role.

### Purpose

- **Canary tasks** have trivially obvious correct answers and are used to detect annotator inattention. They are interspersed across all task type directories.
- **Sentinel tasks** have known-difficult edge cases and are used to verify that scorers handle boundary conditions correctly.

Both task categories deliberately use cross-type placement (e.g., a `canary_001` file in the `negative/` directory) to test that loaders and scorers handle tasks by their `type` field, not by directory membership.


## 4. Inter-Annotator Agreement Process

### Overlap Sampling

- **20% of all examples** are independently scored by two annotators.
- Overlap examples are distributed proportionally across all 11 task types and all 4 difficulty levels.
- Assignment of overlap examples is randomized; annotators do not know which examples are overlap.

### Agreement Metrics

Compute the following metrics on the overlap set, both overall and per task type:

| Metric | Target | Purpose |
|--------|--------|---------|
| Cohen's kappa | >= 0.70 | Measures agreement beyond chance (substantial agreement per Landis-Koch) |
| Spearman rho | >= 0.80 | Measures rank-order agreement on the continuous score scale |
| Kendall's tau | Report alongside Spearman | More robust to ties; no hard threshold but should track Spearman |

### Disagreement Adjudication

1. For any example where the two annotators' scores differ by **> 0.3**, a third annotator independently scores the example.
2. The final gold score is the **median** of the three scores.
3. The adjudicator must also provide a rationale. All three rationales are preserved in the record.
4. If the adjudicator's score is an outlier (differs from both original scores by > 0.3), the example is flagged for rubric review.

### Remediation

- If Cohen's kappa < 0.70 on **any task type**, that task type's rubric is revised:
  1. Collect all disagreement examples for the task type.
  2. Annotators discuss disagreements in a calibration session.
  3. Update the rubric with clarifications or additional scoring criteria.
  4. Re-annotate the task type's overlap set with the revised rubric.
  5. Recompute agreement metrics. Repeat until kappa >= 0.70.
- If kappa < 0.50 after two revision rounds, escalate: consider whether the task type's definition is too ambiguous and revise the task specification.


## 5. Calibration Pipeline

### Phase 1: Rubric Iteration (60 examples)

**Goal:** Refine rubrics before committing to full-scale annotation.

| Step | Action | Output |
|------|--------|--------|
| 1.1  | Select 5-6 examples per task type spanning all difficulty levels | 60 candidate examples |
| 1.2  | Two annotators independently score all 60 examples | 120 score-rationale pairs |
| 1.3  | Compute per-task-type agreement metrics | Agreement report |
| 1.4  | For each task type with kappa < 0.70: hold calibration session, revise rubric | Updated rubrics |
| 1.5  | Re-score disagreement examples with revised rubrics | Revised scores |
| 1.6  | Confirm all task types reach kappa >= 0.70 | Finalized rubrics |

**Exit criterion:** All 11 task types achieve Cohen's kappa >= 0.70 on the Phase 1 overlap set.

### Phase 2: Production Annotation (150+ examples)

**Goal:** Build the full gold standard corpus with finalized rubrics.

| Step | Action | Output |
|------|--------|--------|
| 2.1  | Generate remaining examples to reach 30-50 per task type | Full example set |
| 2.2  | Assign 80% of examples to single annotator, 20% to two annotators (overlap) | Assignment spreadsheet |
| 2.3  | Annotators score independently using finalized rubrics | Raw annotations |
| 2.4  | Compute overlap agreement metrics (overall and per task type) | Agreement report |
| 2.5  | Adjudicate all disagreements > 0.3 via third annotator | Adjudicated scores |
| 2.6  | Compile final gold standard corpus | Gold standard file |

**Exit criterion:** 330+ examples annotated, all task types at kappa >= 0.70 on overlap.

### Phase 3: Validation

**Goal:** Verify the gold standard is suitable for judge calibration.

| Step | Action | Output |
|------|--------|--------|
| 3.1  | Compute overall and per-task-type agreement metrics on production overlap | Final agreement report |
| 3.2  | Flag task types where kappa < 0.70 or Spearman < 0.80 | Flagged task types |
| 3.3  | For flagged task types: revise rubric, re-annotate overlap, recompute | Revised metrics |
| 3.4  | Run LLM judge (GPT-4o) on the full gold standard corpus | Judge predictions |
| 3.5  | Compute judge-vs-gold agreement: Cohen's kappa >= 0.70, Spearman >= 0.80 | Judge calibration report |
| 3.6  | If judge agreement is below threshold on any task type, revise the judge prompt/rubric and re-run | Revised judge config |
| 3.7  | Compute deterministic scorer vs. gold agreement per task type | Scorer calibration report |
| 3.8  | If deterministic scorer disagreement > 15% on any task type, investigate and revise | Revised scorer config |

**Exit criterion:** Both LLM judge and deterministic scorers meet calibration targets against the gold standard.


## 6. Quality Assurance

### Canary Tasks

- **5-10% of all examples** are canary tasks with trivially obvious correct answers.
- Canary examples span all task types (at least 1 per type).
- Canaries are interspersed randomly; annotators are not told which examples are canaries.
- A canary is considered "failed" if the annotator's score deviates from the expected score by > 0.3.

**Enforcement:**
- If an annotator fails **> 10% of canary tasks**, all of their annotations are excluded from the gold standard and reassigned to another annotator.
- If an annotator fails 5-10% of canaries, their non-overlap annotations are spot-checked (10 random examples reviewed by a second annotator).

### Scorer Disagreement Monitoring

When the LLM-judge score and the deterministic scorer score disagree on a gold standard example:

1. Log the disagreement with both scores, the gold score, and the task type.
2. If disagreement rate exceeds **15% on any task type**:
   - Analyze the pattern of disagreements (e.g., "LLM judge scores regex-matching code higher than deterministic scorer").
   - Revise the rubric or scorer configuration to resolve systematic bias.
   - Re-run calibration and recompute agreement metrics.
3. The gold standard score is the tiebreaker in all disagreements.

### Data Integrity

- All annotations are stored with annotator ID, timestamp, and example version.
- Annotations are append-only; corrections create new records rather than overwriting.
- The gold standard corpus is versioned. Any rubric change that triggers re-annotation produces a new version.
- Export format: JSONL with one record per annotation, supporting multiple annotations per example for overlap items.

### Export Schema

```jsonl
{
  "example_id": "retrieval_024",
  "version": "1.0",
  "task_type": "retrieval",
  "difficulty": "medium",
  "question": "Which files handle user authentication?",
  "expected_answer": ["auth/login.py", "auth/middleware.py", "auth/tokens.py"],
  "llm_response": "The authentication files are auth/login.py and auth/middleware.py.",
  "annotations": [
    {
      "annotator_id": "ann_01",
      "score": 0.7,
      "rationale": "Found 2 of 3 expected files. Missed auth/tokens.py. No false positives.",
      "timestamp": "2026-02-06T14:30:00Z",
      "is_adjudication": false
    }
  ],
  "final_score": 0.7,
  "is_canary": false,
  "is_overlap": false
}
```
