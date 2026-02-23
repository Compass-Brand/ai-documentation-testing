"""DS-1000 dataset adapter for code_generation tasks.

DS-1000 contains data science code completion tasks across
NumPy, Pandas, SciPy, Matplotlib, TensorFlow, PyTorch, and Sklearn.

HuggingFace: code-rag-bench/ds1000
License: CC-BY-SA-4.0
Contamination risk: MODERATE (library docs may appear in training data)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


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

            tests = record.get("test", [])
            test_str = "\n".join(tests) if isinstance(tests, list) else str(tests)

            task_id = self._generate_task_id("code_generation", count)
            task = {
                "task_id": task_id,
                "type": "code_generation",
                "question": record.get("prompt", record.get("intent", "")),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["code", "ds1000"] + (record.get("library", []) or []),
                "metadata": {
                    "test": test_str,
                    "canonical_solution": record.get("canonical_solution", ""),
                    "entry_point": record.get("entry_point", ""),
                    "forbidden_patterns": ["eval(", "exec("],
                },
            }
            out_file = output_dir / f"{task_id}.yaml"
            out_file.write_text(
                yaml.dump(task, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            count += 1

        return count

    def build_doc_tree(self, limit: int | None = None) -> "DocTree":
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
