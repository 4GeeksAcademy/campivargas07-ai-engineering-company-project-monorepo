"""Requires confirmed real provider configuration; does not index anything."""
import json
from data.process.config import RagError, settings
from data.process.embeddings import embed
from data.pipelines.rag import generate_answer

if __name__ == '__main__':
    try:
        cfg = settings()
        vector = embed('Programa de puntos de Brasaland', config=cfg)
        answer = generate_answer('¿Qué información tienes?', [], config=cfg)
        print(json.dumps({'embedding_dimensions':len(vector), 'answer':answer},ensure_ascii=False))
    except RagError as exc:
        raise SystemExit(str(exc)) from None
