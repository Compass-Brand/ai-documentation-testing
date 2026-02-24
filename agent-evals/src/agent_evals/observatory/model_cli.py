"""CLI model browser with filtering, sorting, and output formats.

Provides functions for listing, filtering, sorting, and formatting
model metadata for terminal display or machine-readable output.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Sort key mapping: CLI flag -> dict key
_SORT_KEYS: dict[str, str] = {
    "price": "prompt_price",
    "name": "name",
    "context": "context_length",
    "created": "created",
}


def sort_models(
    models: list[dict[str, Any]],
    sort_key: str,
) -> list[dict[str, Any]]:
    """Sort models by the given key. Prefix with '-' for descending."""
    reverse = sort_key.startswith("-")
    key_name = sort_key.lstrip("-")
    dict_key = _SORT_KEYS.get(key_name, key_name)

    return sorted(
        models,
        key=lambda m: m.get(dict_key, 0),
        reverse=reverse,
    )


def fuzzy_search(
    models: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Filter models by fuzzy text match on id and name fields."""
    q = query.lower()
    return [
        m for m in models
        if q in m.get("id", "").lower()
        or q in m.get("name", "").lower()
    ]


def apply_cli_filters(
    models: list[dict[str, Any]],
    *,
    free: bool | None = None,
    max_price: float | None = None,
    min_context: int | None = None,
    modality: str | None = None,
    tokenizer: str | None = None,
    capabilities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Apply CLI filter flags (AND logic)."""
    result = list(models)

    if free is True:
        result = [
            m for m in result
            if m.get("prompt_price", 0) == 0.0
            and m.get("completion_price", 0) == 0.0
        ]

    if max_price is not None:
        result = [
            m for m in result
            if m.get("prompt_price", 0) <= max_price
        ]

    if min_context is not None:
        result = [
            m for m in result
            if m.get("context_length", 0) >= min_context
        ]

    if modality is not None:
        result = [
            m for m in result
            if modality in m.get("modality", "")
        ]

    if tokenizer is not None:
        result = [
            m for m in result
            if m.get("tokenizer", "") == tokenizer
        ]

    if capabilities:
        result = [
            m for m in result
            if all(
                c in m.get("supported_params", [])
                for c in capabilities
            )
        ]

    return result


def format_models_json(models: list[dict[str, Any]]) -> str:
    """Format models as a JSON array string."""
    return json.dumps(models, indent=2)


def format_models_csv(models: list[dict[str, Any]]) -> str:
    """Format models as CSV with header row."""
    if not models:
        return ""

    output = io.StringIO()
    fields = ["id", "name", "prompt_price", "completion_price",
              "context_length", "modality", "tokenizer"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for m in models:
        writer.writerow(m)
    return output.getvalue()


def format_models_table(models: list[dict[str, Any]]) -> str:
    """Format models as a plain-text table for terminal display."""
    if not models:
        return ""

    header = f"{'Name':<30} {'Price In':>10} {'Price Out':>10} {'Context':>10}"
    lines = [header, "-" * len(header)]
    for m in models:
        name = m.get("name", "")[:30]
        price_in = f"${m.get('prompt_price', 0):.6f}"
        price_out = f"${m.get('completion_price', 0):.6f}"
        ctx = str(m.get("context_length", 0))
        lines.append(f"{name:<30} {price_in:>10} {price_out:>10} {ctx:>10}")
    return "\n".join(lines)


def format_model_detail(
    model: dict[str, Any],
    fetch_endpoints: bool = False,
) -> str:
    """Format detailed model information."""
    lines = [
        f"Model: {model.get('name', 'Unknown')}",
        f"ID: {model.get('id', '')}",
        f"Context Length: {model.get('context_length', 0)}",
        f"Prompt Price: ${model.get('prompt_price', 0):.6f}",
        f"Completion Price: ${model.get('completion_price', 0):.6f}",
        f"Modality: {model.get('modality', '')}",
        f"Tokenizer: {model.get('tokenizer', '')}",
    ]

    if fetch_endpoints:
        endpoints = fetch_provider_endpoints(model.get("id", ""))
        if endpoints and "endpoints" in endpoints:
            lines.append("")
            lines.append("Provider Endpoints:")
            for ep in endpoints["endpoints"]:
                provider = ep.get("provider", "Unknown")
                uptime = ep.get("uptime", 0)
                latency = ep.get("latency_ms", 0)
                quant = ep.get("quantization", "none")
                zdr = "ZDR" if ep.get("zdr", False) else ""
                lines.append(
                    f"  {provider}: uptime={uptime}%, "
                    f"latency={latency}ms, quant={quant} {zdr}"
                )
        else:
            lines.append("")
            lines.append("Provider endpoint data unavailable")

    return "\n".join(lines)


def fetch_provider_endpoints(model_id: str) -> dict[str, Any] | None:
    """Fetch provider endpoint data from OpenRouter.

    Returns None on failure.
    """
    try:
        import httpx

        parts = model_id.split("/", 1)
        if len(parts) < 2:
            return None
        resp = httpx.get(
            f"https://openrouter.ai/api/v1/models/{model_id}/endpoints",
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        logger.debug("Failed to fetch endpoints for %s", model_id)
        return None
