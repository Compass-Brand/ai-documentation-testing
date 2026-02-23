"""AmbigQA dataset adapter for disambiguation tasks.

Questions with multiple valid interpretations from Wikipedia context.

HuggingFace: din0s/ambig_qa
License: CC-BY-SA-3.0
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
class AmbigQAAdapter(DatasetAdapter):
    """Adapter for AmbigQA disambiguation tasks."""

    def name(self) -> str:
        return "ambigqa"

    def hf_dataset_id(self) -> str | None:
        return "din0s/ambig_qa"

    def task_type(self) -> str:
        return "disambiguation"

    def domain(self) -> str:
        return "general_knowledge"

    def license(self) -> str:
        return "CC-BY-SA-3.0"

    def contamination_risk(self) -> str:
        return "high"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            annotations = record.get("annotations", {})
            qa_pairs = annotations.get("qaPairs") or []

            interpretations = []
            for i, pair in enumerate(qa_pairs):
                answers = pair.get("answer", [])
                answer_str = answers[0] if answers else "unknown"
                interpretations.append({
                    "label": f"interpretation_{i}",
                    "answer": f"{pair.get('question', '')}: {answer_str}",
                })

            if not interpretations:
                continue

            task_id = self._generate_task_id("disambiguation", count)
            task = {
                "task_id": task_id,
                "type": "disambiguation",
                "question": record.get("question", ""),
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["ambiguous", "wikipedia"],
                "metadata": {
                    "interpretations": interpretations,
                    "expected_interpretation": interpretations[0]["label"],
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
            question = record.get("question", "")
            annotations = record.get("annotations", {})
            qa_pairs = annotations.get("qaPairs") or []

            content_parts = [f"# {question}\n"]
            for pair in qa_pairs:
                answers = pair.get("answer", [])
                content_parts.append(
                    f"- {pair.get('question', '')}: {', '.join(answers)}"
                )
            content = "\n".join(content_parts)

            rid = record.get("id", f"q{idx}")
            rel_path = f"ambigqa/{rid}.md"
            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="reference",
                section="wikipedia",
                summary=question[:100],
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="din0s/ambig_qa",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
