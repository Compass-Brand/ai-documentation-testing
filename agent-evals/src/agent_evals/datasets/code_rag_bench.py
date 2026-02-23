"""CodeRAG-Bench dataset adapter for retrieval tasks.

Pairs code generation queries from code-rag-bench/humaneval with
library-documentation corpus to create retrieval evaluation tasks.

HuggingFace: code-rag-bench/humaneval (queries) + code-rag-bench/library-documentation (corpus)
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
class CodeRAGBenchAdapter(DatasetAdapter):
    """Adapter for CodeRAG-Bench retrieval tasks."""

    _QUERY_DATASET = "code-rag-bench/humaneval"
    _CORPUS_DATASET = "code-rag-bench/library-documentation"

    def name(self) -> str:
        return "code-rag-bench"

    def hf_dataset_id(self) -> str | None:
        return self._QUERY_DATASET

    def task_type(self) -> str:
        return "retrieval"

    def domain(self) -> str:
        return "library_docs"

    def license(self) -> str:
        return "CC-BY-SA-4.0"

    def contamination_risk(self) -> str:
        return "moderate"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        """Download HumanEval queries and write retrieval task YAMLs."""
        ds = load_hf_dataset(self._QUERY_DATASET, split="train")

        count = 0
        for record in ds:
            docs = record.get("docs") or []
            if not docs:
                continue

            if limit is not None and count >= limit:
                break

            expected_files = [
                f"library-docs/{d['title'].replace('.', '/')}.md"
                for d in docs
                if d.get("title")
            ]
            if not expected_files:
                continue

            task_id = self._generate_task_id("retrieval", count)
            task = {
                "task_id": task_id,
                "type": "retrieval",
                "question": record["prompt"],
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["code", "retrieval", "humaneval"],
                "metadata": {
                    "expected_files": expected_files,
                    "evidence_passage": docs[0].get("text", "")[:200],
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
        """Build DocTree from library-documentation corpus."""
        from agent_index.models import DocFile, DocTree

        ds = load_hf_dataset(self._CORPUS_DATASET, split="train", limit=limit)

        files: dict[str, DocFile] = {}
        for idx, record in enumerate(ds):
            if limit is not None and idx >= limit:
                break
            doc_id = record["doc_id"]
            content = record["doc_content"]
            # Derive library name from doc_id (e.g., "numpy.array" -> "numpy")
            lib_name = doc_id.split(".")[0] if "." in doc_id else "general"
            rel_path = f"library-docs/{doc_id.replace('.', '/')}.md"

            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="recommended",
                section=lib_name,
                summary=content[:100].split(".")[0] + "." if "." in content[:100] else content[:100],
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="code-rag-bench/library-documentation",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
