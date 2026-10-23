"""Structured local trace persistence for each LangGraph run (no external paid services)."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from data.process.config import ROOT

DEFAULT_TRACES_DIR = ROOT / "services" / "api" / "data" / "agent_traces"
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def traces_directory(custom_dir: Path | str | None = None) -> Path:
    if custom_dir is not None:
        return Path(custom_dir)
    env_dir = os.getenv("AGENT_TRACES_DIR", "").strip()
    return Path(env_dir) if env_dir else DEFAULT_TRACES_DIR


def sanitize_chunk_summary(chunk: dict[str, Any]) -> dict[str, Any]:
    """Extract observable chunk metadata and text for grounding inspection without internal secrets."""
    return {
        "company": chunk.get("company", "brasaland"),
        "source_document": chunk["source_document"],
        "section": chunk["section"],
        "chunk_index": chunk.get("chunk_index", 0),
        "language": chunk.get("language", "es"),
        "text": chunk["text"],
    }


def save_trace(trace: dict[str, Any], *, directory: Path | str | None = None) -> Path:
    run_id = str(trace.get("run_id", "")).strip()
    if not SAFE_ID_PATTERN.match(run_id):
        raise ValueError("Identificador de corrida inválido para guardar trace.")
    target_dir = traces_directory(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{run_id}.json"
    payload = {
        **trace,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_trace(run_id: str, *, directory: Path | str | None = None) -> dict[str, Any]:
    clean_id = run_id.strip()
    if not SAFE_ID_PATTERN.match(clean_id):
        raise ValueError("Identificador de corrida inválido.")
    path = traces_directory(directory) / f"{clean_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No existe el trace para run_id={clean_id}")
    return json.loads(path.read_text(encoding="utf-8"))
