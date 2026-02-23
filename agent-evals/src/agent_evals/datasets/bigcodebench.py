"""BigCodeBench dataset adapter for compositional tasks.

Multi-API composition tasks requiring use of multiple Python libraries.

HuggingFace: bigcode/bigcodebench
License: Apache-2.0
Contamination risk: MODERATE
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


@register_dataset
class BigCodeBenchAdapter(DatasetAdapter):
    """Adapter for BigCodeBench compositional tasks."""

    def name(self) -> str:
        return "bigcodebench"

    def hf_dataset_id(self) -> str | None:
        return "bigcode/bigcodebench"

    def task_type(self) -> str:
        return "compositional"

    def domain(self) -> str:
        return "library_docs"

    def license(self) -> str:
        return "Apache-2.0"

    def contamination_risk(self) -> str:
        return "moderate"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="train")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            libs = record.get("libs") or []
            prompt = record.get("instruct_prompt") or record.get("complete_prompt", "")

            # Generate sub-questions per library
            sub_questions = [
                f"How would you use the {lib} library for this task?"
                for lib in libs
            ]
            expected_answers = [
                f"Use {lib} API as shown in the solution."
                for lib in libs
            ]

            task_id = self._generate_task_id("compositional", count)
            task = {
                "task_id": task_id,
                "type": "compositional",
                "question": prompt,
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["code", "compositional"] + list(libs),
                "metadata": {
                    "sub_questions": sub_questions,
                    "expected_answers": expected_answers,
                    "composition_type": "multi_library",
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
            libs = record.get("libs") or []
            solution = record.get("canonical_solution", "")
            for lib in libs:
                rel_path = f"bigcodebench/{lib}/api.md"
                if rel_path in files:
                    continue
                content = f"# {lib} API\n\nLibrary used in compositional tasks.\n\n{solution[:500]}"
                files[rel_path] = DocFile(
                    rel_path=rel_path,
                    content=content,
                    size_bytes=len(content.encode("utf-8")),
                    token_count=len(content.split()),
                    tier="recommended",
                    section=lib,
                    summary=f"{lib} library documentation",
                )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="bigcode/bigcodebench",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
