"""Idempotently index the four approved Brasaland manuals."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from data.process.chunking import chunk_documents
from data.process.embeddings import embed, embedding_configuration, validate_embedding
from data.process.loader import COMPANY, CORPUS_REVISION, LANGUAGE, load_documents
from data.process.qdrant_store import (
    COLLECTION_NAME,
    EMBEDDING_CONFIGURATION_KEY,
    create_client,
    ensure_collection,
    validate_configuration,
)

# Fixed project namespace: stable across machines and runs.
CHUNK_NAMESPACE = uuid.UUID("2e6d7ec1-8cc3-5d2e-a8a0-170e2e95d61d")


def setup(
    *,
    client: Any | None = None,
    embedding_fn=embed,
    embedding_config: dict[str, Any] | None = None,
) -> int:
    configuration = validate_configuration(
        embedding_configuration() if embedding_config is None else embedding_config
    )
    documents = load_documents()
    chunks_by_document = {doc.source_document: [] for doc in documents}
    for chunk in chunk_documents(documents):
        chunks_by_document[chunk.source_document].append(chunk)

    owned_client = client is None
    vector_client = client or create_client()
    try:
        dimension = configuration["dimensions"]
        if vector_client.collection_exists(COLLECTION_NAME):
            ensure_collection(vector_client, dimension, embedding_config=configuration, create=False)
        source_by_slug = {doc.source_document: doc for doc in documents}
        all_prepared = []
        for slug, chunks in chunks_by_document.items():
            digest = hashlib.sha256(source_by_slug[slug].text.encode("utf-8")).hexdigest()
            for chunk in chunks:
                vector = validate_embedding(embedding_fn(chunk.text), expected_dimension=dimension)
                point_id = str(uuid.uuid5(CHUNK_NAMESPACE, f"{COMPANY}:{slug}:{chunk.chunk_index}"))
                payload = {
                    "company": COMPANY,
                    "source_document": slug,
                    "section": chunk.section,
                    "language": LANGUAGE,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "source_sha256": digest,
                    "corpus_revision": CORPUS_REVISION,
                    EMBEDDING_CONFIGURATION_KEY: configuration,
                }
                all_prepared.append((slug, point_id, vector, payload))
        if not all_prepared:
            raise ValueError("No document embeddings were produced.")
        ensure_collection(vector_client, dimension, embedding_config=configuration)

        from qdrant_client.http import models

        for slug, points in _group_by_source(all_prepared).items():
            ids = {point_id for point_id, _, _ in points}
            vector_client.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    models.PointStruct(id=point_id, vector=vector, payload=payload)
                    for point_id, vector, payload in points
                ],
                wait=True,
            )
            stale = []
            offset = None
            while True:
                current, offset = vector_client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(key="company", match=models.MatchValue(value=COMPANY)),
                            models.FieldCondition(key="language", match=models.MatchValue(value=LANGUAGE)),
                            models.FieldCondition(key="source_document", match=models.MatchValue(value=slug)),
                        ]
                    ),
                    offset=offset,
                    limit=100,
                    with_payload=False,
                    with_vectors=False,
                )
                stale.extend(point.id for point in current if str(point.id) not in ids)
                if offset is None:
                    break
            if stale:
                vector_client.delete(collection_name=COLLECTION_NAME, points_selector=stale, wait=True)
        return len(all_prepared)
    finally:
        if owned_client:
            vector_client.close()


def _group_by_source(items):
    grouped: dict[str, list] = {}
    for slug, point_id, vector, payload in items:
        grouped.setdefault(slug, []).append((point_id, vector, payload))
    return grouped


if __name__ == "__main__":
    count = setup()
    print(f"Indexed {count} chunks in {COLLECTION_NAME}.")
    for document in load_documents():
        chunks = chunk_documents([document])
        print(f"{document.source_document}: {len(chunks)} chunks")
