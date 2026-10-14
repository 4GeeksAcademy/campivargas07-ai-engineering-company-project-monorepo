"""Vector retrieval with explicit similarity filtering and no score-as-confidence."""

from __future__ import annotations

import os
from typing import Any

from data.process.embeddings import embed, validate_embedding
from data.process.qdrant_store import COLLECTION_NAME, create_client


def retrieve(
    query: str,
    *,
    k: int = 5,
    min_score: float | None = None,
    client: Any | None = None,
    embedding_fn=embed,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    if k < 1:
        raise ValueError("k must be greater than zero")
    threshold = min_score
    if threshold is None:
        configured = os.getenv("KNOWLEDGE_MIN_SCORE")
        if configured is None or not configured.strip():
            raise RuntimeError("KNOWLEDGE_MIN_SCORE must be calibrated and configured.")
        threshold = float(configured)
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("KNOWLEDGE_MIN_SCORE must be within cosine similarity bounds [-1, 1].")

    owned_client = client is None
    vector_client = client or create_client()
    try:
        vector = validate_embedding(embedding_fn(query))
        result = vector_client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )
        matches: list[dict[str, Any]] = []
        for point in result.points:
            score = float(point.score)
            payload = point.payload or {}
            if score < threshold or not isinstance(payload.get("text"), str):
                continue
            matches.append({
                "id": str(point.id),
                "score": score,
                "company": payload.get("company"),
                "source_document": payload.get("source_document"),
                "section": payload.get("section"),
                "language": payload.get("language"),
                "chunk_index": payload.get("chunk_index"),
                "text": payload["text"],
            })
        return matches
    finally:
        if owned_client:
            vector_client.close()
