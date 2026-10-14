from __future__ import annotations

import app.domains.knowledge.router as knowledge_router


def test_knowledge_query_requires_authentication(client, monkeypatch) -> None:
    monkeypatch.setattr(knowledge_router, "query", lambda _question: "respuesta")

    response = client.post("/knowledge/query", json={"question": "¿Qué aplica?"})

    assert response.status_code == 401


def test_knowledge_query_returns_only_answer_and_delegates(
    client, auth_headers, monkeypatch
) -> None:
    questions: list[str] = []

    def fake_query(question: str) -> str:
        questions.append(question)
        return "Consulta el manual oficial."

    monkeypatch.setattr(knowledge_router, "query", fake_query)

    response = client.post(
        "/knowledge/query",
        headers=auth_headers,
        json={"question": "  ¿Qué aplica?  "},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "Consulta el manual oficial."}
    assert questions == ["¿Qué aplica?"]


def test_knowledge_query_hides_upstream_error_details(
    client, auth_headers, monkeypatch
) -> None:
    def fail_query(_question: str) -> str:
        raise RuntimeError("provider-secret-detail")

    monkeypatch.setattr(knowledge_router, "query", fail_query)

    response = client.post(
        "/knowledge/query",
        headers=auth_headers,
        json={"question": "¿Qué aplica?"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "La base de conocimiento no está disponible temporalmente."
    }
    assert "provider-secret-detail" not in response.text