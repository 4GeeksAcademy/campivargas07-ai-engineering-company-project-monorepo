"""Opt-in real-provider preflight. Never invoked by CI or API startup."""
from __future__ import annotations

import argparse
import json
import os

import httpx

from data.pipelines.generation import generate_answer
from data.process.embeddings import embed, embedding_configuration
from data.process.loader import load_documents
from data.process.provider_http import api_base_url, positive_timeout


def list_generation_models() -> list[str]:
    if api_base_url("GENERATION_API_BASE_URL") != "https://api.perplexity.ai/v1":
        raise ValueError("Model discovery is implemented only for Perplexity direct.")
    key = os.getenv("GENERATION_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Set GENERATION_API_KEY locally.")
    with httpx.Client(timeout=positive_timeout("GENERATION_TIMEOUT_SECONDS", "45")) as client:
        response = client.get("https://api.perplexity.ai/v1/models", headers={"Authorization": f"Bearer {key}"})
        response.raise_for_status()
        body = response.json()
    models = body["data"]
    if not isinstance(models, list) or any(not isinstance(item.get("id"), str) for item in models):
        raise ValueError("Unexpected model discovery response.")
    return [item["id"] for item in models]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-generation-models", action="store_true")
    args = parser.parse_args()
    try:
        if args.list_generation_models:
            print(json.dumps({"model_ids": list_generation_models()}, ensure_ascii=False))
        else:
            # Use literal official evidence rather than inventing a smoke policy.
            manual = next(doc for doc in load_documents() if doc.source_document == "loyalty-program")
            question = "¿Cuántos puntos necesito para el nivel Oro y qué beneficios tiene?"
            vector = embed(question)
            answer = generate_answer(question, f"Fuente: loyalty-program\n{manual.text}")
            print(json.dumps({"embedding_configuration": embedding_configuration(), "dimension": len(vector),
                              "question": question, "answer": answer}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Provider exceptions may carry request URLs/headers: print only type.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "action": "Check local model configuration and credentials; no provider details printed."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
