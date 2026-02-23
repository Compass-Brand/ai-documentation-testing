"""RepLiQA dataset adapter for negative (unanswerable) tasks.

RepLiQA (Realistic, Linguistic, Quality Assurance) is a dataset of
synthetically generated documents with human-written QA pairs.
~20% of questions are deliberately unanswerable from the given document.

HuggingFace: ServiceNow/repliqa
License: CC-BY-4.0
Contamination risk: LOW (synthetic documents never in training data)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


@register_dataset
class RepliQAAdapter(DatasetAdapter):
    """Adapter for ServiceNow/repliqa unanswerable subset."""

    def name(self) -> str:
        return "repliqa"

    def hf_dataset_id(self) -> str | None:
        return "ServiceNow/repliqa"

    def task_type(self) -> str:
        return "negative"

    def domain(self) -> str:
        return "synthetic_docs"

    def license(self) -> str:
        return "CC-BY-4.0"

    def contamination_risk(self) -> str:
        return "low"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        """Download RepLiQA and write unanswerable subset as negative tasks."""
        ds = load_hf_dataset(self.hf_dataset_id(), split="repliqa_0")

        unanswerable = [r for r in ds if r["answer"] == "UNANSWERABLE"]

        if limit is not None:
            unanswerable = unanswerable[:limit]

        for idx, record in enumerate(unanswerable):
            task_id = self._generate_task_id("negative", idx)
            task = {
                "task_id": task_id,
                "type": "negative",
                "question": record["question"],
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["synthetic", "repliqa", record["document_topic"]],
                "metadata": {
                    "expected_answer": "unanswerable",
                    "reason": (
                        f"The document covers topic '{record['document_topic']}' "
                        f"but does not contain information to answer this question."
                    ),
                    "nearest_doc": record["document_path"],
                    "nearest_content": record["document_extracted"][:200],
                },
            }
            out_file = output_dir / f"{task_id}.yaml"
            out_file.write_text(
                yaml.dump(task, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )

        return len(unanswerable)

    def build_doc_tree(self, limit: int | None = None) -> "DocTree":
        """Build DocTree from unique RepLiQA documents."""
        from agent_index.models import DocFile, DocTree

        ds = load_hf_dataset(self.hf_dataset_id(), split="repliqa_0")

        seen: dict[str, dict] = {}
        for record in ds:
            doc_id = record["document_id"]
            if doc_id not in seen:
                seen[doc_id] = record
                if limit is not None and len(seen) >= limit:
                    break

        files: dict[str, DocFile] = {}
        for doc_id, record in seen.items():
            content = record["document_extracted"]
            rel_path = f"repliqa/{record['document_topic']}/{doc_id}.md"
            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="required",
                section=record["document_topic"],
                summary=content[:100].split(".")[0] + "." if "." in content[:100] else content[:100],
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="ServiceNow/repliqa",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
