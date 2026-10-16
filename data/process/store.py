"""Qdrant compatibility and ownership boundary shared by setup and retrieval."""
from contextlib import contextmanager
from qdrant_client import QdrantClient, models
from data.process.config import COLLECTION, OWNER, Settings, StoreError


def owned_filter() -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="company", match=models.MatchValue(value="brasaland")),
                              models.FieldCondition(key="managed_by", match=models.MatchValue(value=OWNER))])


@contextmanager
def connection(config: Settings, client=None):
    owned = client is None
    try:
        if owned:
            client = QdrantClient(url=config.qdrant_url, api_key=config.qdrant_key, timeout=config.timeout)
        yield client
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError("No se pudo completar la operación en la base de conocimiento") from exc
    finally:
        if owned and client is not None:
            client.close()


def check_collection(client, config: Settings, *, create=False):
    if not client.collection_exists(COLLECTION):
        if not create:
            raise StoreError("La colección aún no está indexada")
        client.create_collection(COLLECTION, vectors_config={config.vector_name: models.VectorParams(
            size=config.dimension, distance=models.Distance.COSINE)})
    vectors = client.get_collection(COLLECTION).config.params.vectors
    if not isinstance(vectors, dict) or set(vectors) != {config.vector_name}:
        raise StoreError("Colección incompatible con el contrato de embeddings; no se modificó")
    vector = vectors[config.vector_name]
    if vector.size != config.dimension or vector.distance != models.Distance.COSINE:
        raise StoreError("Dimensión o distancia incompatible; no se modificó")
