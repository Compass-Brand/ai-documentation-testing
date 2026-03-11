"""WikiContradict dataset adapter for conflicting tasks.

Contradicting claims from Wikipedia articles.

HuggingFace: ibm-research/Wikipedia_contradict_benchmark
License: MIT
Contamination risk: HIGH (Wikipedia-derived)

Actual columns: WikipediaArticleTitle, context1, context2, answer1,
answer2, question, contradictType, ref_answer, merged_context, url
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_dataset
class WikiContradictAdapter(DatasetAdapter):
    """Adapter for WikiContradict conflicting tasks."""

    def name(self) -> str:
        return "wikicontradict"

    def hf_dataset_id(self) -> str | None:
        return "ibm-research/Wikipedia_contradict_benchmark"

    def task_type(self) -> str:
        return "conflicting"

    def domain(self) -> str:
        return "general_knowledge"

    def license(self) -> str:
        return "MIT"

    def contamination_risk(self) -> str:
        return "high"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            context_1 = record.get("context1", "")
            context_2 = record.get("context2", "")
            answer_1 = record.get("answer1", "")
            answer_2 = record.get("answer2", "")
            article = record.get("WikipediaArticleTitle", "")
            question = record.get("question", "")
            contradict_type = record.get("contradictType", "")

            task_id = self._generate_task_id("conflicting", count)
            task = {
                "task_id": task_id,
                "type": "conflicting",
                "question": (
                    f"The article '{article}' contains contradicting claims: "
                    f"'{answer_1}' vs '{answer_2}'. {question}"
                ),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["contradiction", "wikipedia", contradict_type],
                "metadata": {
                    "sources": [
                        {
                            "name": article,
                            "claim": answer_1,
                            "context": context_1,
                            "authority": 5,
                        },
                        {
                            "name": article,
                            "claim": answer_2,
                            "context": context_2,
                            "authority": 5,
                        },
                    ],
                    "expected_resolution": record.get("ref_answer", ""),
                    "resolution_strategy": "explicit_flag",
                    "contradict_type": contradict_type,
                    "ref_answer": record.get("ref_answer", ""),
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
            article = record.get(
                "WikipediaArticleTitle", f"article_{idx}",
            )
            ctx1 = record.get("context1", "")
            ctx2 = record.get("context2", "")
            question = record.get("question", "")

            content = (
                f"# {article}\n\n"
                f"## Context 1\n{ctx1}\n\n"
                f"## Context 2\n{ctx2}\n\n"
                f"## Question\n{question}"
            )
            safe_name = article.replace(" ", "_").replace("/", "_")
            rel_path = f"wikicontradict/{safe_name}_{idx}.md"
            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="reference",
                section="wikipedia",
                summary=f"Contradicting claims about {article}",
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="ibm-research/Wikipedia_contradict_benchmark",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
