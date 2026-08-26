from pathlib import Path
import sys

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from app.main import app
from app.domains.analytics.incidents import service as incidents_service

FIXTURE = REPO_ROOT / "docs" / "incidents-brasaland.csv"


def test_analyze_fixture_returns_expected_totals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("incidents-brasaland.csv", handle, "text/csv")},
            headers=auth_headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_records"] == 100
    assert payload["valid_records"] == 96
    assert payload["invalid_records"] == 4
    assert payload["satisfaction"]["average_score"] == 3.46


def test_export_requires_previous_analysis(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    incidents_service._latest_analysis = None
    response = client.get("/api/incidents/results/export", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "No analysis results are available yet."


def test_analyze_rejects_invalid_headers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("broken.csv", b"bad,headers\n1,2\n", "text/csv")},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Invalid CSV headers" in response.json()["detail"]