from __future__ import annotations

import runpy
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from qdrant_client import QdrantClient, models

from data.pipelines.query import query
from data.pipelines.retrieval import retrieve
from data.process.loader import COMPANY, CORPUS_REVISION, LANGUAGE, SourceDocument
from data.process.qdrant_store import COLLECTION_NAME, EMBEDDING_CONFIGURATION_KEY, ensure_collection
from data.process.setup import setup


def make_client(dimension: int = 3) -> QdrantClient:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
    return client


def configuration(dimension: int = 3, **changes) -> dict:
    return {
        "provider": "openai_compatible",
        "endpoint": "https://embeddings.example.test/v1",
        "model": "test-embedding",
        "dimensions": dimension,
        "encoding_format": "float",
        "preprocessing": "identity-v1",
        **changes,
    }


def payload(text: str, *, dimension: int = 2, **changes) -> dict:
    return {
        "company": COMPANY,
        "language": LANGUAGE,
        "corpus_revision": CORPUS_REVISION,
        "source_document": "loyalty-program",
        "text": text,
        EMBEDDING_CONFIGURATION_KEY: configuration(dimension),
        **changes,
    }


def make_chunk(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        source_document="loyalty-program",
        chunk_index=index,
        section="Reglas",
        text=f"Regla {index}",
    )


def test_setup_is_idempotent_and_keeps_required_payload() -> None:
    client = QdrantClient(":memory:")
    embedding = lambda _text: [1.0, 0.0, 0.0]
    try:
        first_count = setup(client=client, embedding_fn=embedding, embedding_config=configuration())
        first_points = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )[0]
        second_count = setup(client=client, embedding_fn=embedding, embedding_config=configuration())
        second_points = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )[0]

        assert first_count == second_count == 18
        assert {point.id for point in first_points} == {point.id for point in second_points}
        assert client.count(COLLECTION_NAME, exact=True).count == 18
        required = {"company", "source_document", "section", "language", "chunk_index", "text"}
        assert all(required <= point.payload.keys() for point in second_points)
        assert all(point.payload[EMBEDDING_CONFIGURATION_KEY] == configuration() for point in second_points)
    finally:
        client.close()


def test_setup_removes_stale_chunks_for_updated_document() -> None:
    client = QdrantClient(":memory:")
    document = SourceDocument(
        source_document="loyalty-program",
        title="Lealtad",
        path=Path("loyalty.md"),
        text="Contenido oficial",
    )
    try:
        with (
            patch("data.process.setup.load_documents", return_value=[document]),
            patch(
                "data.process.setup.chunk_documents",
                side_effect=[[make_chunk(0), make_chunk(1)], [make_chunk(0)]],
            ),
        ):
            setup(client=client, embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration())
            setup(client=client, embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration())

        points = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )[0]
        assert len(points) == 1
        assert points[0].payload["chunk_index"] == 0
    finally:
        client.close()


def test_setup_rejects_dimension_mismatch_without_recreating_collection() -> None:
    client = make_client(dimension=2)
    try:
        with pytest.raises(ValueError, match="dimension mismatch"):
            setup(client=client, embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration())
        assert client.get_collection(COLLECTION_NAME).config.params.vectors.size == 2
        assert client.count(COLLECTION_NAME, exact=True).count == 0
    finally:
        client.close()


def test_retrieve_filters_threshold_and_returns_fewer_than_k_or_none() -> None:
    client = make_client(dimension=2)
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=[1.0, 0.0],
                payload=payload("Coincidencia alta"),
            ),
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.0, 1.0],
                payload=payload("Coincidencia baja", source_document="waste-protocol"),
            ),
        ],
        wait=True,
    )
    try:
        fewer = retrieve(
            "pregunta",
            k=5,
            min_score=0.9,
            client=client,
            embedding_fn=lambda _text: [1.0, 0.0],
            embedding_config=configuration(2),
        )
        none = retrieve(
            "pregunta",
            k=5,
            min_score=0.5,
            client=client,
            embedding_fn=lambda _text: [-1.0, 0.0],
            embedding_config=configuration(2),
        )
        assert [item["text"] for item in fewer] == ["Coincidencia alta"]
        assert none == []
    finally:
        client.close()


def test_query_passes_empty_context_and_returns_generated_text() -> None:
    expected_answer = "Respuesta simulada del generador."
    with (
        patch("data.pipelines.query.retrieve", return_value=[]),
        patch("data.pipelines.query.generate_answer", return_value=expected_answer) as generate,
    ):
        answer = query("¿Qué dice el manual?")

    assert answer == expected_answer
    generate.assert_called_once_with("¿Qué dice el manual?", "")


@pytest.mark.parametrize("changes", [
    {"provider": "perplexity"},
    {"endpoint": "https://another-provider.example.test/v1"},
    {"model": "another-model"},
    {"encoding_format": "base64_int8"},
    {"preprocessing": "another-preprocessing"},
])
def test_setup_rejects_changed_embedding_identity_without_mutating_points(changes: dict) -> None:
    client = QdrantClient(":memory:")
    try:
        setup(client=client, embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration())
        before = client.scroll(COLLECTION_NAME, limit=100, with_vectors=True, with_payload=True)[0]
        with (
            patch.object(client, "upsert") as upsert,
            patch.object(client, "delete") as delete,
            patch.object(client, "delete_collection") as delete_collection,
            pytest.raises(ValueError, match="embedding configuration mismatch"),
        ):
            setup(
                client=client,
                embedding_fn=lambda _text: [1.0, 0.0, 0.0],
                embedding_config=configuration(**changes),
            )
        upsert.assert_not_called()
        delete.assert_not_called()
        delete_collection.assert_not_called()
        assert client.scroll(COLLECTION_NAME, limit=100, with_vectors=True, with_payload=True)[0] == before
    finally:
        client.close()


def test_existing_points_without_identity_require_explicit_migration() -> None:
    client = make_client(2)
    point = models.PointStruct(id=str(uuid.uuid4()), vector=[1.0, 0.0], payload={"text": "legacy"})
    client.upsert(COLLECTION_NAME, [point])
    try:
        with pytest.raises(ValueError, match="missing metadata"):
            setup(client=client, embedding_fn=lambda _text: [1.0, 0.0], embedding_config=configuration(2))
        with pytest.raises(ValueError, match="missing metadata"):
            retrieve(
                "pregunta", min_score=0.1, client=client,
                embedding_fn=lambda _text: [1.0, 0.0], embedding_config=configuration(2),
            )
        stored = client.retrieve(COLLECTION_NAME, ids=[point.id], with_vectors=True)[0]
        assert stored.payload == point.payload
        assert stored.vector == [1.0, 0.0]
    finally:
        client.close()


def test_collection_identity_validation_reads_all_pages() -> None:
    client = make_client(2)
    points = [
        models.PointStruct(id=index, vector=[1.0, 0.0], payload=payload("compatible"))
        for index in range(101)
    ]
    points[-1].payload[EMBEDDING_CONFIGURATION_KEY] = configuration(2, model="incompatible")
    client.upsert(COLLECTION_NAME, points)
    try:
        with pytest.raises(ValueError, match="embedding configuration mismatch"):
            ensure_collection(client, 2, embedding_config=configuration(2), create=False)
        assert client.count(COLLECTION_NAME, exact=True).count == 101
    finally:
        client.close()


def test_setup_rejects_non_cosine_collection_without_mutation() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(COLLECTION_NAME, vectors_config=models.VectorParams(size=3, distance=models.Distance.DOT))
    try:
        with pytest.raises(ValueError, match="cosine distance"):
            setup(client=client, embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration())
        assert client.get_collection(COLLECTION_NAME).config.params.vectors.distance == models.Distance.DOT
        assert client.count(COLLECTION_NAME, exact=True).count == 0
    finally:
        client.close()


@pytest.mark.parametrize("vector", [[], [0.0, 0.0], [1.0], [1.0, float("nan")], [True, 1.0]])
def test_setup_invalid_vector_does_not_create_collection(vector: list) -> None:
    client = QdrantClient(":memory:")
    try:
        with pytest.raises(ValueError):
            setup(client=client, embedding_fn=lambda _text: vector, embedding_config=configuration(2))
        assert not client.collection_exists(COLLECTION_NAME)
    finally:
        client.close()


@pytest.mark.parametrize("changes", [
    {"dimensions": 3}, {"model": "another-model"}, {"encoding_format": "base64_int8"},
    {"preprocessing": "another-preprocessing"}, {"provider": "perplexity"},
    {"endpoint": "https://another-provider.example.test/v1"},
])
def test_retrieve_rejects_incompatible_collection_before_query(changes: dict) -> None:
    client = make_client(2)
    client.upsert(COLLECTION_NAME, [models.PointStruct(id=0, vector=[1.0, 0.0], payload=payload("evidencia"))])
    try:
        with (
            patch.object(client, "query_points") as query_points,
            pytest.raises(ValueError, match="mismatch"),
        ):
            retrieve(
                "pregunta", min_score=0.1, client=client,
                embedding_fn=lambda _text: [1.0, 0.0], embedding_config=configuration(2, **changes),
            )
        query_points.assert_not_called()
    finally:
        client.close()


def test_retrieve_rejects_query_vector_dimension_before_sending_query() -> None:
    client = make_client(2)
    try:
        with (
            patch.object(client, "query_points") as query_points,
            pytest.raises(ValueError, match="dimension mismatch"),
        ):
            retrieve(
                "pregunta", min_score=0.1, client=client,
                embedding_fn=lambda _text: [1.0, 0.0, 0.0], embedding_config=configuration(2),
            )
        query_points.assert_not_called()
    finally:
        client.close()


def test_retrieve_does_not_create_missing_collection() -> None:
    client = QdrantClient(":memory:")
    try:
        with pytest.raises(ValueError, match="has not been indexed"):
            retrieve(
                "pregunta", min_score=0.1, client=client,
                embedding_fn=lambda _text: [1.0, 0.0], embedding_config=configuration(2),
            )
        assert not client.collection_exists(COLLECTION_NAME)
    finally:
        client.close()


def test_retrieve_limits_k_and_filters_company_corpus_language_and_source() -> None:
    client = make_client(2)
    payloads = [
        payload("otro tenant", company="another-company"),
        payload("otra revisión", corpus_revision="old-corpus"),
        payload("otro idioma", language="en"),
        payload("fuera del corpus", source_document="incident-context"),
        payload("oficial uno"),
        payload("oficial dos"),
    ]
    client.upsert(COLLECTION_NAME, [
        models.PointStruct(id=index, vector=[1.0, 0.0], payload=item)
        for index, item in enumerate(payloads)
    ])
    try:
        results = retrieve(
            "pregunta", k=1, min_score=0.1, client=client,
            embedding_fn=lambda _text: [1.0, 0.0], embedding_config=configuration(2),
        )
        assert len(results) == 1
        assert results[0]["text"] in {"oficial uno", "oficial dos"}
        assert EMBEDDING_CONFIGURATION_KEY not in results[0]
    finally:
        client.close()


@pytest.mark.parametrize("k", [0, -1, True, 1.5, "3"])
def test_retrieve_rejects_invalid_k(k) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        retrieve("pregunta", k=k, min_score=0.1)


@pytest.mark.parametrize("threshold", [-1.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_retrieve_rejects_invalid_threshold(threshold) -> None:
    with pytest.raises(ValueError, match="cosine similarity bounds"):
        retrieve("pregunta", min_score=threshold)


def test_retrieve_requires_calibrated_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KNOWLEDGE_MIN_SCORE", raising=False)
    with pytest.raises(RuntimeError, match="calibrated"):
        retrieve("pregunta")


def test_setup_module_cli_runs_indexing_and_reports_sources(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    client = QdrantClient(":memory:")
    original_close = client.close
    monkeypatch.setattr("data.process.embeddings.embed", lambda _text: [1.0, 0.0])
    monkeypatch.setattr("data.process.embeddings.embedding_configuration", lambda: configuration(2))
    monkeypatch.setattr("data.process.qdrant_store.create_client", lambda: client)
    monkeypatch.setattr(client, "close", lambda: None)
    try:
        with patch.dict(sys.modules):
            sys.modules.pop("data.process.setup", None)
            runpy.run_module("data.process.setup", run_name="__main__")
        output = capsys.readouterr().out
        assert "Indexed 18 chunks in brasaland_knowledge" in output
        for source in ("loyalty-program", "waste-protocol", "menu-allergens", "supplier-ordering"):
            assert f"{source}: " in output
        assert client.count(COLLECTION_NAME, exact=True).count == 18
    finally:
        original_close()
