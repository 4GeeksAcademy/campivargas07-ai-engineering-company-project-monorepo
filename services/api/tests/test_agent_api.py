"""Contract and security tests for POST /agent/query (coexisting with POST /knowledge/query)."""
import pytest

from app.domains.agent import router as agent_router
from app.domains.knowledge import router as knowledge_router
from data.process.config import ConfigurationError, ProviderError, StoreError


def test_agent_auth_required(client, monkeypatch):
    monkeypatch.setattr(agent_router, "execute_agent_query", lambda *a, **kw: pytest.fail("No anonymous agent execution"))
    assert client.post("/agent/query", json={"question": "puntos"}).status_code in (401, 403)


def test_agent_invalid_token_rejected(client, monkeypatch):
    monkeypatch.setattr(agent_router, "execute_agent_query", lambda *a, **kw: pytest.fail("No invalid token execution"))
    response = client.post(
        "/agent/query",
        headers={"Authorization": "Bearer invalid-token"},
        json={"question": "puntos"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_agent_inactive_user_rejected(client, create_test_user, monkeypatch):
    from app.domains.auth.service import create_access_token

    user = create_test_user(is_active=False)
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})
    monkeypatch.setattr(agent_router, "execute_agent_query", lambda *a, **kw: pytest.fail("No inactive user execution"))
    response = client.post(
        "/agent/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "puntos"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [{}, {"question": ""}, {"question": "   "}, {"question": "x" * 2001}, {"question": 3}, {"question": "q", "extra": 1}],
)
def test_agent_request_validation(client, auth_headers, body):
    assert client.post("/agent/query", headers=auth_headers, json=body).status_code == 422


def test_agent_returns_serialized_answer_and_coexists_with_knowledge(client, auth_headers, monkeypatch):
    seen_agent = []
    seen_knowledge = []
    monkeypatch.setattr(
        agent_router,
        "execute_agent_query",
        lambda q, **kwargs: seen_agent.append((q, kwargs)) or {
            "run_id": "run-test",
            "thread_id": "run-test",
            "answer": "Respuesta agente",
            "route": "grounded",
        },
    )
    monkeypatch.setattr(
        knowledge_router,
        "query",
        lambda q: seen_knowledge.append(q) or "Respuesta knowledge",
    )

    res_agent = client.post("/agent/query", headers=auth_headers, json={"question": "  nivel Oro  "})
    assert res_agent.status_code == 200
    assert res_agent.json() == {"answer": "Respuesta agente"}
    assert seen_agent == [("nivel Oro", {"incident_token": auth_headers["Authorization"].removeprefix("Bearer ")})]

    res_knowledge = client.post("/knowledge/query", headers=auth_headers, json={"question": "  nivel Oro  "})
    assert res_knowledge.status_code == 200
    assert res_knowledge.json() == {"answer": "Respuesta knowledge"}
    assert seen_knowledge == ["nivel Oro"]


@pytest.mark.parametrize(
    "error,status",
    [(ConfigurationError, 503), (ProviderError, 502), (StoreError, 503), (RuntimeError, 500)],
)
def test_agent_sanitizes_internal_errors(client, auth_headers, monkeypatch, error, status):
    def fail(_, **kwargs):
        raise error("secret api_key sk-fake-12345 and internal traceback details")

    monkeypatch.setattr(agent_router, "execute_agent_query", fail)
    response = client.post("/agent/query", headers=auth_headers, json={"question": "puntos"})
    assert response.status_code == status
    assert "secret" not in response.text
    assert "sk-fake" not in response.text
    assert "answer" not in response.json()
