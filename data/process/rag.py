"""Run from repository root: python -m data.process.rag (actually calls setup)."""
import json
from collections import Counter
from pathlib import Path
from qdrant_client import models
from data.process.config import COLLECTION, ROOT, RagError, Settings, settings
from data.process.corpus import load_chunks
from data.process.embeddings import embed, validate_vector
from data.process.store import check_collection, connection, owned_filter


def setup(*, config: Settings | None = None, client=None,
          directory: Path = ROOT / "docs/company-knowledge-base", embedder=None) -> dict:
    cfg = config or settings()
    chunks = load_chunks(directory)
    with connection(cfg, client) as store:
        if store.collection_exists(COLLECTION):
            check_collection(store, cfg)
        # Complete embeddings before any write: failed providers cannot erase old data.
        points = [models.PointStruct(id=c["id"], payload=c["payload"], vector={cfg.vector_name:
                  validate_vector(embedder(c["payload"]["text"]) if embedder else
                                  embed(c["payload"]["text"], config=cfg), cfg.dimension)}) for c in chunks]
        check_collection(store, cfg, create=True)
        old_ids, offset = set(), None
        while True:
            records, offset = store.scroll(COLLECTION, scroll_filter=owned_filter(), offset=offset,
                                           limit=256, with_payload=False, with_vectors=False)
            old_ids.update(str(p.id) for p in records)
            if offset is None:
                break
        store.upsert(COLLECTION, points=points, wait=True)
        stale = old_ids - {c["id"] for c in chunks}
        if stale:
            store.delete(COLLECTION, points_selector=models.PointIdsList(points=sorted(stale)), wait=True)
        count = store.count(COLLECTION, count_filter=owned_filter(), exact=True).count
    return {"collection": COLLECTION, "owned_points": count, "removed": len(stale),
            "chunks_per_document": dict(Counter(c["payload"]["source_document"] for c in chunks))}


if __name__ == "__main__":
    try:
        print(json.dumps(setup(), ensure_ascii=False, indent=2))
    except RagError as exc:
        raise SystemExit(str(exc)) from None
