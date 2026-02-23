"""SWE-bench Verified dataset adapter for agentic tasks.

Real GitHub bug reports with repository context for agent evaluation.

HuggingFace: princeton-nlp/SWE-bench_Verified
License: MIT
Contamination risk: HIGH (well-known benchmark)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter


@register_dataset
class SWEBenchAdapter(DatasetAdapter):
    """Adapter for SWE-bench Verified agentic tasks."""

    def name(self) -> str:
        return "swe-bench"

    def hf_dataset_id(self) -> str | None:
        return "princeton-nlp/SWE-bench_Verified"

    def task_type(self) -> str:
        return "agentic"

    def domain(self) -> str:
        return "code_repository"

    def license(self) -> str:
        return "MIT"

    def contamination_risk(self) -> str:
        return "high"

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        ds = load_hf_dataset(self.hf_dataset_id(), split="test")

        count = 0
        for record in ds:
            if limit is not None and count >= limit:
                break

            instance_id = record.get("instance_id", "")
            repo = record.get("repo", "")
            problem = record.get("problem_statement", "")
            hints = record.get("hints_text", "")

            # Parse FAIL_TO_PASS and PASS_TO_PASS (stored as JSON strings)
            fail_to_pass_raw = record.get("FAIL_TO_PASS", "[]")
            pass_to_pass_raw = record.get("PASS_TO_PASS", "[]")
            try:
                fail_to_pass = json.loads(fail_to_pass_raw) if isinstance(fail_to_pass_raw, str) else fail_to_pass_raw
            except (json.JSONDecodeError, TypeError):
                fail_to_pass = []
            try:
                pass_to_pass = json.loads(pass_to_pass_raw) if isinstance(pass_to_pass_raw, str) else pass_to_pass_raw
            except (json.JSONDecodeError, TypeError):
                pass_to_pass = []

            # Build files dict from repo structure
            files = {f"{repo}/docs/README.md": f"Repository documentation for {repo}"}
            if hints:
                files[f"{repo}/hints.md"] = hints[:200]

            task_id = self._generate_task_id("agentic", count)
            task = {
                "task_id": task_id,
                "type": "agentic",
                "question": problem,
                "domain": self.domain(),
                "difficulty": "hard",
                "tags": ["swe-bench", "agentic", repo.split("/")[0] if "/" in repo else repo],
                "metadata": {
                    "files": files,
                    "FAIL_TO_PASS": fail_to_pass,
                    "PASS_TO_PASS": pass_to_pass,
                    "instance_id": instance_id,
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

        ds = load_hf_dataset(self.hf_dataset_id(), split="test", limit=limit)

        files: dict[str, DocFile] = {}
        for idx, record in enumerate(ds):
            if limit is not None and idx >= limit:
                break
            repo = record.get("repo", "unknown")
            problem = record.get("problem_statement", "")
            instance_id = record.get("instance_id", f"instance_{idx}")
            rel_path = f"swe-bench/{instance_id}.md"

            content = f"# {instance_id}\n\nRepository: {repo}\n\n{problem}"
            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="required",
                section=repo.split("/")[0] if "/" in repo else repo,
                summary=problem[:100],
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="princeton-nlp/SWE-bench_Verified",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
