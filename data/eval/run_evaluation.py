"""Run retrieval evaluation against a configured real Qdrant/embedding endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path

from data.pipelines.retrieval import retrieve


def run() -> dict:
    cases = json.loads(Path(__file__).with_name("test-queries.json").read_text(encoding="utf-8"))
    in_scope = [case for case in cases if case["expected_source_document"]]
    results = []
    hits = 0
    for case in in_scope:
        matches = retrieve(case["question"], k=3)
        hit = any(
            item.get("source_document") == case["expected_source_document"]
            and item.get("section") == case["expected_section"]
            for item in matches
        )
        hits += int(hit)
        results.append({"id": case["id"], "hit": hit, "retrieved": matches})
    report = {
        "evaluation_type": "real_retrieval",
        "embedding_model": os.getenv("EMBEDDING_MODEL"),
        "qdrant_url_configured": bool(os.getenv("QDRANT_URL")),
        "min_score": os.getenv("KNOWLEDGE_MIN_SCORE"),
        "in_scope_queries": len(in_scope),
        "recall_at_3": hits / len(in_scope) if in_scope else 0.0,
        "target": 0.8,
        "meets_target": bool(in_scope) and hits / len(in_scope) >= 0.8,
        "results": results,
        "note": "No scores were interpreted as confidence. Out-of-scope cases are excluded from Recall@3.",
    }
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
