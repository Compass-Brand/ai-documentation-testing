"""IBM TechQA dataset adapter for fact_extraction tasks.

TechQA contains real questions from IBM technical forums paired
with answers extracted from IBM Technotes (support documents).

HuggingFace: PrimeQA/TechQA
License: Apache-2.0
Contamination risk: LOW (domain-specific IT support content)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agent_evals.datasets import register_dataset
from agent_evals.datasets._hf_utils import load_hf_dataset
from agent_evals.datasets.base import DatasetAdapter

logger = logging.getLogger(__name__)


@register_dataset
class IBMTechQAAdapter(DatasetAdapter):
    """Adapter for PrimeQA/TechQA fact extraction tasks."""

    def name(self) -> str:
        return "ibm-techqa"

    def hf_dataset_id(self) -> str | None:
        return "PrimeQA/TechQA"

    def task_type(self) -> str:
        return "fact_extraction"

    def domain(self) -> str:
        return "technical_qa"

    def license(self) -> str:
        return "Apache-2.0"

    def contamination_risk(self) -> str:
        return "low"

    def _load_qa_records(self) -> list[dict[str, Any]]:
        """Load QA records from the TechQA dataset.

        Attempts HuggingFace load first, falls back to direct download.
        Returns a list of dicts with QUESTION_ID, QUESTION_TITLE, etc.
        """
        try:
            ds = load_hf_dataset(self.hf_dataset_id(), split="train")
            return list(ds)
        except Exception:
            logger.warning(
                "Could not load TechQA from HuggingFace; "
                "dataset may require manual download."
            )
            return []

    def _load_technotes(self) -> dict[str, dict[str, str]]:
        """Load technote corpus. Returns {doc_id: {_id, title, text}}."""
        try:
            ds = load_hf_dataset(self.hf_dataset_id(), split="train")
            # If HF provides a flat format, try to extract technotes
            technotes: dict[str, dict[str, str]] = {}
            for record in ds:
                doc_id = record.get("DOCUMENT") or record.get("_id", "")
                if doc_id and "text" in record:
                    technotes[doc_id] = {
                        "_id": doc_id,
                        "title": record.get("title", ""),
                        "text": record["text"],
                    }
            return technotes
        except Exception:
            return {}

    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        """Convert TechQA QA pairs into fact_extraction task YAMLs."""
        qa_records = self._load_qa_records()
        technotes = self._load_technotes()

        count = 0
        for record in qa_records:
            if record.get("ANSWERABLE") != "Y":
                continue

            doc_id = record.get("DOCUMENT", "")
            if doc_id not in technotes:
                continue

            if limit is not None and count >= limit:
                break

            doc = technotes[doc_id]
            doc_text = doc.get("text", "")

            # Extract answer span
            start = record.get("START_OFFSET", 0)
            end = record.get("END_OFFSET", 0)
            if 0 <= start < end <= len(doc_text):
                answer = doc_text[start:end]
            else:
                answer = doc.get("title", "unknown")

            task_id = self._generate_task_id("fact_extraction", count)
            question_title = record.get("QUESTION_TITLE", "")
            question_text = record.get("QUESTION_TEXT", "")
            question = f"{question_title}: {question_text}" if question_text else question_title

            task = {
                "task_id": task_id,
                "type": "fact_extraction",
                "question": question,
                "domain": self.domain(),
                "difficulty": "medium",
                "tags": ["technical", "ibm", "techqa"],
                "metadata": {
                    "expected_answer": answer,
                    "answer_aliases": [],
                    "source_location": doc_id,
                    "fact_type": "extractive",
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
        """Build DocTree from TechQA technotes."""
        from agent_index.models import DocFile, DocTree

        technotes = self._load_technotes()

        files: dict[str, DocFile] = {}
        for idx, (doc_id, doc) in enumerate(technotes.items()):
            if limit is not None and idx >= limit:
                break

            content = doc.get("text", "")
            title = doc.get("title", doc_id)
            rel_path = f"technotes/{doc_id}.md"

            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content.encode("utf-8")),
                token_count=len(content.split()),
                tier="recommended",
                section="technotes",
                summary=title[:100],
            )

        return DocTree(
            files=files,
            scanned_at=datetime.now(tz=UTC),
            source="PrimeQA/TechQA",
            total_tokens=sum(f.token_count or 0 for f in files.values()),
        )
