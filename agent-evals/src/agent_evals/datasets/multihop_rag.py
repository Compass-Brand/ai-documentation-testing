"""MultiHop-RAG dataset adapter for multi_hop tasks.

Multi-hop queries requiring reasoning across multiple news articles.

HuggingFace: yixuantt/MultiHopRAG
License: MIT
Contamination risk: MODERATE (news articles may appear in training data)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


@register_dataset
class MultiHopRAGAdapter(DatasetAdapter):
    """Adapter for MultiHop-RAG multi-hop reasoning tasks."""

    def name(self) -> str:
        return "multihop-rag"

    def hf_dataset_id(self) -> str | None:
        return "yixuantt/MultiHopRAG"

    def task_type(self) -> str:
        return "multi_hop"

    def domain(self) -> str:
        return "news_articles"

    def license(self) -> str:
        return "MIT"

    def contamination_risk(self) -> str:
        return "moderate"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            evidence = record.get("evidence_list") or []
            reasoning_chain = [e.get("fact", "") for e in evidence if e.get("fact")]
            question_decomposition = [
                f"Evidence from {e.get('source', 'unknown')}: {e.get('fact', '')}"
                for e in evidence
                if e.get("fact")
            ]

            task_id = self._generate_task_id("multi_hop", count)
            task = {
                "task_id": task_id,
                "type": "multi_hop",
                "question": record.get("query", ""),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["multi-hop", "news", "rag"],
                "metadata": {
                    "reasoning_chain": reasoning_chain,
                    "question_decomposition": question_decomposition,
                    "paragraphs": [
                        {"source": e.get("source", ""), "text": e.get("fact", "")}
                        for e in evidence
                    ],
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
            evidence = record.get("evidence_list") or []
            for e in evidence:
                source = e.get("source", "")
                fact = e.get("fact", "")
                if not source or not fact:
                    continue
                rel_path = f"news/{source}.md"
                if rel_path in files:
                    # Append to existing doc
                    existing = files[rel_path]
                    files[rel_path] = existing.model_copy(
                        update={"content": existing.content + "\n\n" + fact},
                    )
                else:
                    files[rel_path] = DocFile(
                        rel_path=rel_path,
                        content=fact,
                        size_bytes=len(fact.encode("utf-8")),
                        token_count=len(fact.split()),
                        tier="recommended",
                        section="news",
                        summary=fact[:100],
                    )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="yixuantt/MultiHopRAG",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
