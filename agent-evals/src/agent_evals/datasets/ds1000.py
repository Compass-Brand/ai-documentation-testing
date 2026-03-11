"""DS-1000 dataset adapter for code_generation tasks.

DS-1000 contains data science code completion tasks across
NumPy, Pandas, SciPy, Matplotlib, TensorFlow, PyTorch, and Sklearn.

HuggingFace: code-rag-bench/ds1000
License: CC-BY-SA-4.0
Contamination risk: MODERATE (library docs may appear in training data)
"""

from __future__ import annotations

import ast
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _extract_key_patterns(reference_code: str) -> list[str]:
    """Extract key expressions from DS-1000 reference code for literal matching.

    DS-1000 reference code typically follows the pattern::

        def g(df, List):
            return df.iloc[List]

        result = g(df.copy(), List)

    This function extracts the meaningful expressions (e.g. ``df.iloc[List]``)
    that should appear in a correct answer, rather than storing the full
    wrapper function as a test pattern (bug #169).

    Strategy:
    1. Parse the code with ``ast`` to find return statements and
       standalone expressions inside function bodies.
    2. If parsing fails, fall back to heuristic line extraction.
    3. Filter out boilerplate lines (function defs, result assignments,
       blank lines, comments).
    """
    patterns: list[str] = []
    code = textwrap.dedent(reference_code).strip()

    # Try AST-based extraction first
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.Return) and child.value is not None:
                        # Extract the source text of the return value
                        pattern = ast.get_source_segment(code, child.value)
                        if pattern and pattern.strip():
                            patterns.append(pattern.strip())
                    elif isinstance(child, ast.Expr):
                        pattern = ast.get_source_segment(code, child.value)
                        if pattern and pattern.strip():
                            patterns.append(pattern.strip())
    except SyntaxError:
        pass

    # Try top-level assignments: `result = expr` or `x = expr`
    if not patterns:
        try:
            tree = ast.parse(code)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    value = ast.get_source_segment(code, node.value)
                    if value and value.strip():
                        patterns.append(value.strip())
        except SyntaxError:
            pass

    # Fallback: heuristic line extraction if AST found nothing
    if not patterns:
        patterns = _extract_patterns_heuristic(code)

    return patterns


def _extract_patterns_heuristic(code: str) -> list[str]:
    """Heuristic fallback for extracting key patterns from reference code.

    Filters out boilerplate lines and returns substantive code lines.
    """
    skip_prefixes = ("def ", "result ", "result=", "#", "import ")
    patterns: list[str] = []
    for line in code.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(p) for p in skip_prefixes):
            continue
        if stripped.startswith("return "):
            # Keep just the return expression
            expr = stripped[len("return "):].strip()
            if expr:
                patterns.append(expr)
            continue
        patterns.append(stripped)
    return patterns


@register_dataset
class DS1000Adapter(DatasetAdapter):
    """Adapter for DS-1000 code generation tasks."""

    def name(self) -> str:
        return "ds1000"

    def hf_dataset_id(self) -> str | None:
        return "code-rag-bench/ds1000"

    def task_type(self) -> str:
        return "code_generation"

    def domain(self) -> str:
        return "library_docs"

    def license(self) -> str:
        return "CC-BY-SA-4.0"

    def contamination_risk(self) -> str:
        return "moderate"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            ref_code = record.get("reference_code", "")
            meta = record.get("metadata") or {}
            library = meta.get("library", "unknown")

            # Extract key expressions for literal pattern matching (bug #169)
            test_patterns = _extract_key_patterns(ref_code)
            test_field = "\n".join(test_patterns)

            task_id = self._generate_task_id("code_generation", count)
            task = {
                "task_id": task_id,
                "type": "code_generation",
                "question": record.get("prompt", ""),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["code", "ds1000", library],
                "metadata": {
                    "test": test_field,
                    "canonical_solution": ref_code,
                    "entry_point": "",
                    "forbidden_patterns": ["eval(", "exec("],
                    "library": library,
                    "code_context": record.get("code_context", ""),
                },
            }
            out_file = output_dir / f"{task_id}.yaml"
            out_file.write_text(
                yaml.dump(task, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            count += 1

        return count

    def build_doc_tree(self, limit: int | None = None) -> DocTree:
        from agent_index.models import DocFile, DocTree

        ds = load_hf_dataset(self.hf_dataset_id(), split="train", limit=limit)

        files: dict[str, DocFile] = {}
        for idx, record in enumerate(ds):
            if limit is not None and idx >= limit:
                break
            docs = record.get("docs") or []
            for doc in docs:
                title = doc.get("title", "")
                text = doc.get("text", "")
                if not title or not text:
                    continue
                rel_path = f"ds1000/{title.replace('.', '/')}.md"
                if rel_path in files:
                    continue
                lib = title.split(".")[0] if "." in title else "general"
                files[rel_path] = DocFile(
                    rel_path=rel_path,
                    content=text,
                    size_bytes=len(text.encode("utf-8")),
                    token_count=len(text.split()),
                    tier="recommended",
                    section=lib,
                    summary=title,
                )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="code-rag-bench/ds1000",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
