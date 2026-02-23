"""WikiContradict dataset adapter for conflicting tasks.

Contradicting claims from Wikipedia articles.

HuggingFace: ibm-research/Wikipedia_contradict_benchmark
License: CC-BY-4.0
Contamination risk: HIGH (Wikipedia-derived)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


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
        return "CC-BY-4.0"

    def contamination_risk(self) -> str:
        return "high"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            statement_1 = record.get("statement_1", "")
            statement_2 = record.get("statement_2", "")
            section_1 = record.get("section_1", "")
            section_2 = record.get("section_2", "")
            article = record.get("article_title", "")

            task_id = self._generate_task_id("conflicting", count)
            task = {
                "task_id": task_id,
                "type": "conflicting",
                "question": (
                    f"The article '{article}' contains contradicting claims: "
                    f"'{statement_1}' vs '{statement_2}'. Which is correct?"
                ),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["contradiction", "wikipedia"],
                "metadata": {
                    "sources": [
                        {
                            "name": f"{article} ({section_1})",
                            "claim": statement_1,
                            "authority": 5,
                        },
                        {
                            "name": f"{article} ({section_2})",
                            "claim": statement_2,
                            "authority": 5,
                        },
                    ],
                    "expected_resolution": (
                        f"These statements from '{article}' contradict each other "
                        f"and require verification against authoritative sources."
                    ),
                    "resolution_strategy": "explicit_flag",
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
            article = record.get("article_title", f"article_{idx}")
            s1 = record.get("statement_1", "")
            s2 = record.get("statement_2", "")

            content = f"# {article}\n\n{s1}\n\n{s2}"
            rel_path = f"wikicontradict/{article.replace(' ', '_')}.md"
            if rel_path not in files:
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
