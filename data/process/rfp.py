"""Reusable transformations for RFP intake (Parte 1).

Business-specific rules (department list, classification criteria, handoff contract)
are intentionally NOT hardcoded here: they must come from the official RFP BRIEFING.
This module exposes:
- pdf_to_markdown: convert a PDF to Markdown before any agent reads it.
- compute_readability: readability metrics with language/content limitations.
- extract_metadata: generic metadata extraction hook (criteria from BRIEFING).
- classify_rfp: classifier hook that is BLOCKED until official criteria exist.
- decompose_departments / worker_extract / synthesize / build_handoff: hooks blocked
  until the official BRIEFING defines departments and contract.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class RfpBlockedError(RuntimeError):
    """Raised when an RFP step requires the official BRIEFING that is missing."""


def _read_text_config(name: str) -> str:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "config" / name,
        root / "docs" / "rfp" / name,
    ]
    for c in candidates:
        if c.exists():
            return c.read_text(encoding="utf-8")
    return ""


def _read_json_config(name: str) -> Any:
    raw = _read_text_config(name)
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def pdf_to_markdown(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts: list[str] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        parts.append(f"## Page {idx + 1}\n\n{text.strip()}")
    return "\n\n".join(parts).strip()


def compute_readability(markdown: str, language: str = "unknown") -> list[dict[str, Any]]:
    """Return a list of metric dicts: name, value, language, limitations_note."""
    results: list[dict[str, Any]] = []
    base_limitations = (
        "Readability metrics (py-readability-metrics) are calibrated primarily for English; "
        "for non-English text (e.g. Spanish) scores are informational and not directly comparable. "
        "Converted PDF Markdown may include tables/lists/non-narrative fragments that distort indices. "
        "Metrics are informational and never gate acceptance/rejection."
    )
    try:
        from readability import Readability

        r = Readability(markdown)
        candidates = [
            ("flesch_reading_ease", lambda x: x.flesch().score),
            ("flesch_kincaid_grade", lambda x: x.flesch_kincaid().score),
            ("gunning_fog", lambda x: x.gunning_fog().score),
            ("smog_index", lambda x: x.smog().score),
            ("coleman_liau", lambda x: x.coleman_liau().score),
            ("automated_readability_index", lambda x: x.automated_readability_index().score),
        ]
        for name, fn in candidates:
            try:
                value = float(fn(r))
                results.append(
                    {
                        "metric_name": name,
                        "value": value,
                        "language": language,
                        "limitations_note": base_limitations,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "metric_name": name,
                        "value": 0.0,
                        "language": language,
                        "limitations_note": f"{base_limitations} (unavailable: {exc})",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        results.append(
            {
                "metric_name": "readability_unavailable",
                "value": 0.0,
                "language": language,
                "limitations_note": f"{base_limitations} (library error: {exc})",
            }
        )
    return results


def extract_metadata(markdown: str) -> dict[str, Any]:
    """Generic metadata extraction hook.

    The concrete fields/criteria come from the official RFP BRIEFING.
    Until then, returns an empty dict and records that extraction is pending.
    """
    criteria = _read_text_config("rfp_metadata_fields.md")
    if not criteria.strip():
        return {"_status": "blocked", "_reason": "official RFP BRIEFING metadata fields not provided"}
    # Placeholder for BRIEFING-driven extraction.
    return {"_status": "pending_implementation", "_criteria_loaded": True}


def classify_rfp(markdown: str, metadata: dict[str, Any]) -> dict[str, Any]:
    criteria = _read_text_config("rfp_classification_criteria.md")
    if not criteria.strip():
        raise RfpBlockedError(
            "Official RFP BRIEFING classification criteria not provided; classifier blocked."
        )
    # BRIEFING-driven implementation pending.
    raise RfpBlockedError("Classifier implementation pending official criteria.")


def load_departments() -> list[str]:
    data = _read_json_config("rfp_departments.json")
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


def decompose_departments(markdown: str, metadata: dict[str, Any]) -> list[str]:
    departments = load_departments()
    if not departments:
        raise RfpBlockedError("Official RFP BRIEFING department list not provided.")
    return departments


def worker_extract(department: str, markdown: str, metadata: dict[str, Any]) -> dict[str, Any]:
    # Returns {"aspects": [...], "contacts": [...]} without inventing figures.
    criteria = _read_text_config("rfp_department_data.md")
    if not criteria.strip():
        raise RfpBlockedError(
            f"Official RFP BRIEFING data requirements for department '{department}' not provided."
        )
    raise RfpBlockedError("Worker implementation pending official criteria.")


def synthesize(ticket_id: str, department_results: list[dict[str, Any]]) -> dict[str, Any]:
    contract = _read_text_config("rfp_handoff_contract.md")
    if not contract.strip():
        raise RfpBlockedError("Official RFP handoff contract not provided.")
    raise RfpBlockedError("Synthesizer implementation pending official contract.")


def build_handoff(ticket_id: str, synthesis: dict[str, Any], department_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "key_aspects": synthesis.get("key_aspects", []),
        "workstreams": synthesis.get("workstreams", []),
    }


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
