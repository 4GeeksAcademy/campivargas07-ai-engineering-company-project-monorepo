from __future__ import annotations

from fastapi.testclient import TestClient
from tinydb import TinyDB

from app.domains.auth.service import create_access_token


def test_health_has_explicit_json_contract(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith("application/json")


def test_user_responses_never_expose_password_hash(
    client: TestClient, create_test_user
) -> None:
    user = create_test_user(email="serializacion@brasaland.com")
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/users", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["users"]
    assert all("password" not in item for item in payload["users"])
    assert all("hashed_password" not in item for item in payload["users"])


def test_delete_user_has_explicit_confirmation_contract(
    client: TestClient, create_test_user
) -> None:
    admin = create_test_user(email="admin-serializacion@brasaland.com", role="admin")
    target = create_test_user(email="target-serializacion@brasaland.com")
    token = create_access_token(data={"sub": str(admin.doc_id), "role": "admin"})

    response = client.delete(
        f"/users/{target.doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"detail": "User and linked profile deleted"}


def test_openapi_declares_special_response_models(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"]
    delete_response = schema["paths"]["/users/{user_id}"]["delete"]["responses"]["200"]
    assert delete_response["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DeleteResponse"
    )