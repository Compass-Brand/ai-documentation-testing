"""AmbigQA dataset adapter for disambiguation tasks.

Questions with multiple valid interpretations from Wikipedia context.

HuggingFace: sewon/ambig_qa (light config)
License: CC-BY-SA-3.0
Contamination risk: HIGH (Wikipedia-derived)
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
class AmbigQAAdapter(DatasetAdapter):
    """Adapter for AmbigQA disambiguation tasks."""

    def name(self) -> str:
        return "ambigqa"

    def hf_dataset_id(self) -> str | None:
        return "sewon/ambig_qa"

    def task_type(self) -> str:
        return "disambiguation"

    def domain(self) -> str:
        return "general_knowledge"

    def license(self) -> str:
        return "CC-BY-SA-3.0"

    def contamination_risk(self) -> str:
        return "high"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train", name="light")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            annotations = record.get("annotations", {})
            ann_type = annotations.get("type", [])
            qa_pairs = annotations.get("qaPairs") or []

            # Skip singleAnswer records -- they have only 1 interpretation,
            # so the disambiguation scorer trivially returns 1.0 (bug #179).
            if ann_type and ann_type[0] == "singleAnswer":
                continue

            interpretations = []

            # multipleQAs: interpretations are in qaPairs as parallel arrays
            if ann_type and ann_type[0] == "multipleQAs" and qa_pairs:
                container = qa_pairs[0]
                questions = container.get("question", [])
                answers = container.get("answer", [])
                for i, (q, ans_list) in enumerate(zip(questions, answers)):
                    answer_str = ans_list[0] if ans_list else "unknown"
                    interpretations.append({
                        "label": f"interpretation_{i}",
                        "answer": f"{q}: {answer_str}",
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

    def build_doc_tree(self, limit: int | None = None) -> DocTree:
        from agent_index.models import DocFile, DocTree

        ds = load_hf_dataset(
            self.hf_dataset_id(), split="train", limit=limit, name="light",
        )

        files: dict[str, DocFile] = {}
        for idx, record in enumerate(ds):
            if limit is not None and idx >= limit:
                break
            question = record.get("question", "")
            annotations = record.get("annotations", {})
            qa_pairs = annotations.get("qaPairs") or []

            content_parts = [f"# {question}\n"]
            if qa_pairs:
                container = qa_pairs[0]
                questions = container.get("question", [])
                answers = container.get("answer", [])
                for q, ans_list in zip(questions, answers):
                    content_parts.append(
                        f"- {q}: {', '.join(ans_list)}"
                    )

            # Fallback to annotations.answer for singleAnswer
            if len(content_parts) == 1:
                ann_answers = annotations.get("answer", [])
                if ann_answers and ann_answers[0]:
                    content_parts.append(f"- {', '.join(ann_answers[0])}")

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
            source="sewon/ambig_qa",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
