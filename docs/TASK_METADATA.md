# Task Metadata Reference

Each gold-standard YAML task has a `metadata` field (`dict[str, Any]`) whose expected keys depend on the task's `type`. This document lists the metadata fields read by each task type's scorer, derived from the concrete `EvalTask.__init__` implementations.

All fields are optional at the Pydantic level (metadata defaults to `{}`), but a scorer will return 0.0 or degrade gracefully if its expected fields are missing.

---

## retrieval

Evaluates file-path identification accuracy using F-beta (beta=2, recall-weighted).

**Source:** `agent-evals/src/agent_evals/tasks/retrieval.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_files` | `list[str]` | File paths the response should mention. Compared with path normalization and fuzzy basename matching. |
| `evidence_passage` | `str` | A passage from the docs supporting the expected files (for human review, not used in scoring). |

```yaml
task_id: retrieval_001
type: retrieval
question: "Which files document the authentication middleware?"
domain: framework_api
difficulty: easy
metadata:
  expected_files:
    - "api/auth.md"
    - "middleware/auth-middleware.md"
  evidence_passage: "AuthMiddleware handles JWT token validation"
```

---

## fact_extraction

Evaluates factual answer accuracy via exact match, alias match, or keyword fraction fallback.

**Source:** `agent-evals/src/agent_evals/tasks/fact_extraction.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_answer` | `str` | The canonical correct answer. Exact case-insensitive match yields 1.0. |
| `answer_aliases` | `list[str]` | Alternative phrasings that also count as correct (each checked case-insensitively). |
| `source_location` | `str` | File path or section where the fact originates (for traceability, not scored). |
| `fact_type` | `str` | Category of fact (e.g. "config_value", "version", "api_endpoint") for analysis. |

```yaml
task_id: fact_extraction_001
type: fact_extraction
question: "What port does the dev server use by default?"
domain: framework_api
difficulty: easy
metadata:
  expected_answer: "3000"
  answer_aliases:
    - "port 3000"
    - "localhost:3000"
  source_location: "docs/getting-started.md"
  fact_type: "config_value"
```

---

## code_generation

Evaluates generated code via regex pattern matching, forbidden-pattern violations, and Python syntax validation.

**Source:** `agent-evals/src/agent_evals/tasks/code_generation.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_answer` | `str` | Reference answer text. |
| `test` | `str` | Newline-separated regex patterns. Each is matched (case-insensitive) against the response. Match rate contributes 70% of score. |
| `entry_point` | `str` | Expected function/class name. |
| `canonical_solution` | `str` | Gold-standard code solution for reference. |
| `libs` | `list[str]` | Expected library imports. |
| `doc_struct` | `dict[str, object]` | Structural hints about the documentation (e.g. relevant sections). |
| `forbidden_patterns` | `list[str]` | Regex patterns that must NOT appear. Violation rate contributes 20% penalty. |

```yaml
task_id: code_generation_001
type: code_generation
question: "Write a function that validates JWT tokens using the auth middleware"
domain: framework_api
difficulty: medium
metadata:
  expected_answer: "def validate_token(token: str) -> bool"
  test: |
    def validate_token
    jwt\.decode
    return\s+(True|False)
  entry_point: "validate_token"
  canonical_solution: "def validate_token(token): ..."
  libs:
    - "jwt"
    - "datetime"
  forbidden_patterns:
    - "eval\\("
    - "exec\\("
```

---

## agentic

Evaluates multi-step coding agent behaviour via file-path mentions, content keywords, tool usage, and test-name mentions.

**Source:** `agent-evals/src/agent_evals/tasks/agentic.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_tools` | `list[dict[str, Any]]` | List of tool dicts with at least a `name` key. When present, tool-usage scoring is enabled (coverage, ordering, precision). |
| `files` | `dict[str, str]` | Map of file_path -> content summary. Keys checked for path mentions; values used for keyword overlap. |
| `setup_script` | `str` | Shell script to set up the project context. |
| `FAIL_TO_PASS` | `str \| list[str]` | Test names that should fail before the fix and pass after. JSON string or list. |
| `PASS_TO_PASS` | `str \| list[str]` | Test names that should continue passing. JSON string or list. |
| `message_limit` | `int` | Maximum number of agent messages allowed. |
| `token_limit` | `int` | Maximum token budget for the agent interaction. |

```yaml
task_id: agentic_001
type: agentic
question: "Fix the failing authentication test by updating the token validation logic"
domain: project_repo
difficulty: hard
metadata:
  expected_tools:
    - name: read_file
    - name: edit_file
    - name: run_tests
  files:
    "src/auth/validator.py": "JWT token validation with expiry checking"
    "tests/test_auth.py": "Unit tests for token validation"
  FAIL_TO_PASS: '["test_expired_token_rejected"]'
  PASS_TO_PASS: '["test_valid_token_accepted"]'
  message_limit: 10
  token_limit: 8000
```

---

## multi_hop

Evaluates multi-step reasoning by checking keyword coverage of each reasoning-chain step.

**Source:** `agent-evals/src/agent_evals/tasks/multi_hop.py`

| Field | Type | Description |
|-------|------|-------------|
| `paragraphs` | `list[dict[str, Any]]` | Evidence paragraphs from multiple sources. |
| `question_decomposition` | `list[str]` | Sub-questions the main question decomposes into. Used as fallback if reasoning_chain is empty. |
| `reasoning_chain` | `list[str]` | Expected factual answers for each reasoning step. Keywords are extracted and matched against the response. |

```yaml
task_id: multi_hop_001
type: multi_hop
question: "What authentication method does the API gateway use and where is it configured?"
domain: framework_api
difficulty: medium
metadata:
  paragraphs:
    - source: "api/gateway.md"
      content: "The API gateway delegates auth to AuthMiddleware"
    - source: "config/auth.yaml"
      content: "auth_method: jwt, issuer: auth.example.com"
  question_decomposition:
    - "What authentication method does the gateway use?"
    - "Where is the authentication configured?"
  reasoning_chain:
    - "JWT authentication via AuthMiddleware"
    - "Configured in config/auth.yaml with issuer auth.example.com"
```

---

## negative

Evaluates correct abstention on unanswerable questions by detecting abstention phrases.

**Source:** `agent-evals/src/agent_evals/tasks/negative.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_answer` | `str` | Description of why the question is unanswerable. |
| `reason` | `str` | Human-readable explanation of why no answer exists in the docs. |
| `nearest_doc` | `str` | The most relevant (but insufficient) document path. |
| `nearest_content` | `str` | Content from the nearest doc that might mislead the agent. |
| `answerable` | `bool` | Legacy field. Always `false` for negative tasks. |
| `distractor_files` | `list[str]` | Legacy field. Files that look relevant but do not contain the answer. |

```yaml
task_id: negative_001
type: negative
question: "What is the maximum file upload size for the API?"
domain: framework_api
difficulty: medium
metadata:
  expected_answer: "The documentation does not specify upload size limits"
  reason: "No file upload configuration is documented anywhere"
  nearest_doc: "api/endpoints.md"
  nearest_content: "POST /files endpoint accepts multipart uploads"
```

---

## compositional

Evaluates multi-part questions by checking sub-task answer coverage.

**Source:** `agent-evals/src/agent_evals/tasks/compositional.py`

| Field | Type | Description |
|-------|------|-------------|
| `composition_type` | `str` | Category of composition (e.g. "compare", "aggregate", "sequential"). |
| `sub_tasks` | `list[dict[str, Any]]` | List of `{question, expected_answer}` dicts. Score = fraction whose `expected_answer` appears in the response. |
| `sub_questions` | `list[str]` | Alternative format: parallel list of sub-questions (used when `sub_tasks` is absent). |
| `expected_answers` | `list[str]` | Alternative format: parallel list of expected answers (paired with `sub_questions`). |

```yaml
task_id: compositional_001
type: compositional
question: "Compare the authentication methods used by the API gateway and the admin panel"
domain: framework_api
difficulty: hard
metadata:
  composition_type: "compare"
  sub_tasks:
    - question: "What auth method does the API gateway use?"
      expected_answer: "JWT"
    - question: "What auth method does the admin panel use?"
      expected_answer: "session-based cookies"
```

---

## robustness

Evaluates answer stability under input perturbation. Uses the same scoring as fact_extraction (exact/alias/keyword match).

**Source:** `agent-evals/src/agent_evals/tasks/robustness.py`

| Field | Type | Description |
|-------|------|-------------|
| `base_task_id` | `str` | The task_id of the original (unperturbed) task this derives from. |
| `perturbation_type` | `str` | Type of perturbation applied (e.g. "paraphrase", "typo", "reorder"). |
| `expected_answer` | `str` | The canonical correct answer (same as the base task). |
| `answer_aliases` | `list[str]` | Alternative correct phrasings. |

```yaml
task_id: robustness_001
type: robustness
question: "Wat port does teh dev server defualt to?"  # intentional typos
domain: framework_api
difficulty: medium
metadata:
  base_task_id: "fact_extraction_001"
  perturbation_type: "typo"
  expected_answer: "3000"
  answer_aliases:
    - "port 3000"
```

---

## disambiguation

Evaluates interpretation selection from ambiguous alternatives.

**Source:** `agent-evals/src/agent_evals/tasks/disambiguation.py`

| Field | Type | Description |
|-------|------|-------------|
| `interpretations` | `list[dict[str, Any]]` | List of `{label, answer}` dicts representing possible interpretations. |
| `expected_interpretation` | `str` | The `label` of the correct interpretation. |

Scoring: 1.0 if >= 50% of the expected answer's keywords appear in the response; 0.5 if the label (or its underscore-normalized form) appears; 0.0 otherwise.

```yaml
task_id: disambiguation_001
type: disambiguation
question: "How do you configure the router?"
domain: framework_api
difficulty: medium
metadata:
  expected_interpretation: "api_router"
  interpretations:
    - label: "api_router"
      answer: "Configure routes in config/routes.yaml with path, method, and handler fields"
    - label: "network_router"
      answer: "Network routing is configured via the infrastructure Ansible playbooks"
```

---

## conflicting

Evaluates conflict resolution when multiple sources disagree.

**Source:** `agent-evals/src/agent_evals/tasks/conflicting.py`

| Field | Type | Description |
|-------|------|-------------|
| `sources` | `list[dict[str, Any]]` | List of source dicts with conflicting claims (e.g. `{file, claim, authority}`). |
| `expected_resolution` | `str` | The correct resolved answer. Exact match yields 1.0; fallback uses keyword fraction. |
| `resolution_strategy` | `str` | The strategy for resolving the conflict (e.g. "highest_authority", "most_recent"). |

```yaml
task_id: conflicting_001
type: conflicting
question: "What is the default database connection timeout?"
domain: framework_api
difficulty: hard
metadata:
  sources:
    - file: "docs/database.md"
      claim: "Default timeout is 30 seconds"
      authority: "official"
    - file: "docs/legacy/database.md"
      claim: "Default timeout is 60 seconds"
      authority: "deprecated"
  expected_resolution: "30 seconds"
  resolution_strategy: "highest_authority"
```

---

## efficiency

Evaluates answer correctness with a length penalty for exceeding a token budget.

**Source:** `agent-evals/src/agent_evals/tasks/efficiency.py`

| Field | Type | Description |
|-------|------|-------------|
| `expected_answer` | `str` | The canonical correct answer. |
| `answer_aliases` | `list[str]` | Alternative correct phrasings. |
| `token_budget` | `int` | Maximum word count (approximated as tokens). Responses exceeding this are penalized by `budget / actual`. |
| `message_limit` | `int` | Maximum number of agent messages allowed (for future agentic efficiency tasks). |

```yaml
task_id: efficiency_001
type: efficiency
question: "What is the default log level?"
domain: framework_api
difficulty: easy
metadata:
  expected_answer: "INFO"
  answer_aliases:
    - "info"
    - "logging.INFO"
  token_budget: 50
```
