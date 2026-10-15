"""Authenticated API -> actual pipeline -> Qdrant local -> HTTP fixtures.

This validates wiring, never real-provider fidelity or Recall.
"""
from __future__ import annotations

import base64
import json

import httpx
import pytest
from qdrant_client import QdrantClient

from data.pipelines.generation import INSUFFICIENT_ANSWER
from data.process.qdrant_store import COLLECTION_NAME
from data.process.setup import setup


@pytest.mark.parametrize("scenario", ["grounded", "empty", "provider_error", "rejected_grounding"])
def test_authenticated_pipeline_wiring_with_offline_http(client, auth_headers, monkeypatch, scenario):
    settings = {
        "EMBEDDING_PROVIDER": "perplexity", "EMBEDDING_API_BASE_URL": "https://api.perplexity.ai/v1",
        "EMBEDDING_MODEL": "pplx-embed-v1-0.6b", "EMBEDDING_DIMENSIONS": "128",
        "EMBEDDING_ENCODING_FORMAT": "base64_int8", "EMBEDDING_API_KEY": "fixture-only",
        "GENERATION_PROVIDER": "perplexity", "GENERATION_API_BASE_URL": "https://api.perplexity.ai/v1",
        "GENERATION_MODEL": "vendor/fixture-only", "GENERATION_API_KEY": "fixture-only",
        "KNOWLEDGE_MIN_SCORE": "0.9",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    original_client = httpx.Client
    calls = []
    question = "¿Cuántos puntos necesito para el nivel Oro?" if scenario != "empty" else "¿Horario de Miami?"
    grounded_answer = "El nivel Oro requiere 50+ puntos y ofrece 15% de descuento permanente. Fuente: loyalty-program."

    def handler(request):
        body = json.loads(request.content)
        calls.append(request.url.path)
        if request.url.path.endswith("/embeddings"):
            text = body["input"]
            axis = 0 if "Oro" in text else 1
            raw = bytearray(128)
            raw[axis] = 127
            if text == question and scenario == "empty":
                raw = bytearray(128)
                raw[0] = 128  # opposite the Oro vector; no matches >= .9
            return httpx.Response(200, json={"model": body["model"], "data": [
                {"index": 0, "embedding": base64.b64encode(raw).decode()},
            ]})
        assert request.url.path == "/v1/agent"
        assert body["tools"] == [] and body["tool_choice"] == "none"
        context = json.loads(body["input"])["untrusted_context"]
        if scenario == "provider_error":
            return httpx.Response(429, json={"error": "private-provider-detail"})
        answer = INSUFFICIENT_ANSWER if not context else grounded_answer
        if scenario == "rejected_grounding":
            answer = "El nivel Oro requiere 999 puntos."
        if scenario == "empty":
            assert context == ""
        else:
            assert "Oro (50+ puntos)" in context
        return httpx.Response(200, json={"model": body["model"], "status": "completed", "output": [
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": answer}]},
        ]})

    monkeypatch.setattr("data.process.provider_http.httpx.Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    store = QdrantClient(":memory:")
    real_close = store.close
    try:
        monkeypatch.setattr("data.pipelines.retrieval.create_client", lambda: store)
        # Keep ownership with the fixture until the request has completed.
        monkeypatch.setattr(store, "close", lambda: None)
        assert setup(client=store) == setup(client=store) == 18
        assert store.count(COLLECTION_NAME, exact=True).count == 18
        calls.clear()
        response = client.post("/knowledge/query", json={"question": question}, headers=auth_headers)
    finally:
        real_close()
    assert calls == ["/v1/embeddings", "/v1/agent"]
    if scenario in {"provider_error", "rejected_grounding"}:
        assert response.status_code == 503
        assert response.json() == {"detail": "La base de conocimiento no está disponible temporalmente."}
        assert "999" not in response.text and "private-provider-detail" not in response.text
    else:
        assert response.status_code == 200
        assert response.json() == {"answer": INSUFFICIENT_ANSWER if scenario == "empty" else grounded_answer}
    assert not {"chunks", "payload", "score", "vector", "retrieved"} & response.json().keys()
