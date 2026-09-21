"""Integration tests for the authenticated incident manager API."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB

from app.domains.incidents.persistence import IncidentRepository
from app.domains.incidents.router import _get_service
from app.domains.incidents.service import IncidentService
from app.main import app


SAMPLE_INCIDENT = {
    "title": "Equipo de refrigeración fuera de servicio",
    "description": "El equipo principal dejó de funcionar durante el turno.",
    "category": "EQUIPMENT",
    "branch": "COL-06",
}


@pytest.fixture(autouse=True)
def isolated_incident_service(tmp_path) -> Generator[IncidentService, None, None]:
    database = TinyDB(tmp_path / "incidents.json")
    service = IncidentService(IncidentRepository(database.table("incidents")))
    app.dependency_overrides[_get_service] = lambda: service
    yield service
    app.dependency_overrides.pop(_get_service, None)
    database.close()


def create_incident(
    client: TestClient,
    auth_headers: dict[str, str],
    payload: dict | None = None,
) -> dict:
    response = client.post(
        "/api/incidents",
        json=payload or SAMPLE_INCIDENT,
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def test_incident_endpoints_require_authentication(client: TestClient):
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/incidents/summary").status_code == 401
    assert client.post("/api/incidents", json=SAMPLE_INCIDENT).status_code == 401


def test_create_and_get_incident(client: TestClient, auth_headers: dict[str, str]):
    created = create_incident(client, auth_headers)

    assert created["status"] == "open"
    assert created["origin"] == "api"
    response = client.get(f"/api/incidents/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == created


def test_create_validation_uses_incident_error_contract(
    client: TestClient,
    auth_headers: dict[str, str],
):
    response = client.post("/api/incidents", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert response.json()["request_id"]
    assert "title" in response.json()["message"]


def test_incident_validation_does_not_change_other_domains(
    client: TestClient,
    auth_headers: dict[str, str],
):
    response = client.post(
        "/api/suppliers",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_list_incidents_with_filters(client: TestClient, auth_headers: dict[str, str]):
    create_incident(client, auth_headers)
    create_incident(
        client,
        auth_headers,
        {
            **SAMPLE_INCIDENT,
            "title": "Falta de insumos en cocina",
            "category": "SUPPLY",
            "branch": "FLA-01",
        },
    )

    by_category = client.get(
        "/api/incidents?category=SUPPLY",
        headers=auth_headers,
    )
    by_branch = client.get(
        "/api/incidents?branch=COL-06",
        headers=auth_headers,
    )

    assert [item["category"] for item in by_category.json()] == ["SUPPLY"]
    assert [item["branch"] for item in by_branch.json()] == ["COL-06"]


def test_incident_summary_aggregates_dimensions(
    client: TestClient,
    auth_headers: dict[str, str],
):
    create_incident(client, auth_headers)
    response = client.get("/api/incidents/summary", headers=auth_headers)

    assert response.status_code == 200
    summary = response.json()
    assert summary["total"] == 1
    assert summary["by_status"][0]["status"] == "open"
    assert summary["by_category"][0]["category"] == "EQUIPMENT"


def test_valid_status_transitions(client: TestClient, auth_headers: dict[str, str]):
    created = create_incident(client, auth_headers)
    path = f"/api/incidents/{created['id']}/status"

    in_progress = client.patch(
        path,
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    resolved = client.patch(
        path,
        json={"status": "resolved"},
        headers=auth_headers,
    )

    assert in_progress.status_code == 200
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_invalid_and_terminal_transitions_are_rejected(
    client: TestClient,
    auth_headers: dict[str, str],
):
    first = create_incident(client, auth_headers)
    invalid = client.patch(
        f"/api/incidents/{first['id']}/status",
        json={"status": "resolved"},
        headers=auth_headers,
    )

    second = create_incident(
        client,
        auth_headers,
        {**SAMPLE_INCIDENT, "title": "Incidente descartable"},
    )
    path = f"/api/incidents/{second['id']}/status"
    client.patch(path, json={"status": "discarded"}, headers=auth_headers)
    terminal = client.patch(path, json={"status": "open"}, headers=auth_headers)

    assert invalid.status_code == 400
    assert terminal.status_code == 400


def test_unknown_incident_returns_404(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/api/incidents/not-found", headers=auth_headers)
    assert response.status_code == 404
