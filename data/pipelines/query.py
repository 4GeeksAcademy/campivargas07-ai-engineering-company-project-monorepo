"""Public composition function for the Brasaland knowledge assistant."""

from __future__ import annotations

from data.pipelines.generation import generate_answer
from data.pipelines.retrieval import retrieve


def query(question: str) -> str:
    results = retrieve(question, k=5)
    context = "\n\n---\n\n".join(
        f"Fuente: {item.get('source_document')} — sección: {item.get('section')}\n{item['text']}"
        for item in results
    )
    return generate_answer(question, context)
