"""Public composition function for the Brasaland knowledge assistant."""

from __future__ import annotations

from data.pipelines.generation import generate_answer
from data.pipelines.retrieval import retrieve


def build_context(results: list[dict]) -> str:
    """Use one evidence rendering for the API and real evaluation."""
    return "\n\n---\n\n".join(
        f"Fuente: {item.get('source_document')} — sección: {item.get('section')}\n{item['text']}"
        for item in results
    )


def query(question: str) -> str:
    return generate_answer(question, build_context(retrieve(question, k=5)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Consulta real al corpus oficial de Brasaland")
    parser.add_argument("question")
    args = parser.parse_args()
    print(query(args.question))
