"""Vector retrieval with explicit similarity filtering and no score-as-confidence."""

from __future__ import annotations

import math
import os
from typing import Any

from data.process.embeddings import embed, embedding_configuration, validate_embedding
from data.process.loader import COMPANY, CORPUS_REVISION, LANGUAGE, SOURCE_FILES
from data.process.qdrant_store import (
    COLLECTION_NAME,
    EMBEDDING_CONFIGURATION_KEY,
    create_client,
    ensure_collection,
    validate_configuration,
)


def retrieve(
    query: str,
    *,
    k: int = 5,
    min_score: float | None = None,
    client: Any | None = None,
    embedding_fn=embed,
    embedding_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if not query.strip():
        return []
    threshold = min_score
    if threshold is None:
        configured = os.getenv("KNOWLEDGE_MIN_SCORE")
        if configured is None or not configured.strip():
            raise RuntimeError("KNOWLEDGE_MIN_SCORE must be calibrated and configured.")
        threshold = float(configured)
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not -1.0 <= threshold <= 1.0
    ):
        raise ValueError("KNOWLEDGE_MIN_SCORE must be within cosine similarity bounds [-1, 1].")
    configuration = validate_configuration(
        embedding_configuration() if embedding_config is None else embedding_config
    )

    owned_client = client is None
    vector_client = client or create_client()
    try:
        from qdrant_client.http import models

        ensure_collection(
            vector_client,
            configuration["dimensions"],
            embedding_config=configuration,
            create=False,
        )
        vector = validate_embedding(embedding_fn(query), expected_dimension=configuration["dimensions"])
        conditions = [
            models.FieldCondition(key="company", match=models.MatchValue(value=COMPANY)),
            models.FieldCondition(key="language", match=models.MatchValue(value=LANGUAGE)),
            models.FieldCondition(key="corpus_revision", match=models.MatchValue(value=CORPUS_REVISION)),
            models.FieldCondition(key="source_document", match=models.MatchAny(any=list(SOURCE_FILES))),
        ]
        conditions.extend(
            models.FieldCondition(
                key=f"{EMBEDDING_CONFIGURATION_KEY}.{key}",
                match=models.MatchValue(value=value),
            )
            for key, value in configuration.items()
        )
        result = vector_client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=k,
            query_filter=models.Filter(must=conditions),
            score_threshold=threshold,
            with_payload=True,
            with_vectors=False,
        )
        matches: list[dict[str, Any]] = []
        for point in result.points:
            score = float(point.score)
            payload = point.payload or {}
            if (
                not math.isfinite(score)
                or score < threshold
                or not isinstance(payload.get("text"), str)
                or payload.get("company") != COMPANY
                or payload.get("language") != LANGUAGE
                or payload.get("corpus_revision") != CORPUS_REVISION
                or not isinstance(payload.get("source_document"), str)
                or payload.get("source_document") not in SOURCE_FILES
                or payload.get(EMBEDDING_CONFIGURATION_KEY) != configuration
            ):
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
        return matches[:k]
    finally:
        if owned_client:
            vector_client.close()
