"""Authenticated, read-only HTTP client for the existing incident API."""
from enum import StrEnum
import os
import re
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.incidents.constants import CATEGORY_LABELS, VALID_BRANCHES, VALID_STATUSES_API

INCIDENT_TOOL_TIMEOUT_SECONDS = 5.0
INCIDENT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{12}$")


class IncidentToolStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class IncidentToolInput(BaseModel):
    """Only accepts the actual incident API ID or its supported list filters."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    status: str | None = None
    category: str | None = None
    branch: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_STATUSES_API:
            raise ValueError("Unsupported incident status filter.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is not None and value not in CATEGORY_LABELS:
            raise ValueError("Unsupported incident category filter.")
        return value

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str | None) -> str | None:
        if value is not None and value.upper() not in VALID_BRANCHES:
            raise ValueError("Unsupported incident branch filter.")
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_query(self):
        if self.incident_id is not None and any(
            value is not None for value in (self.status, self.category, self.branch)
        ):
            raise ValueError("Use an incident ID or list filters, not both.")
        return self


class IncidentRecord(BaseModel):
    """The operational fields needed by the agent; free-text fields are excluded."""

    model_config = ConfigDict(extra="ignore")

    id: str
    category: str
    status: str
    branch: str
    reported_at: str
    updated_at: str
    origin: str
    external_ref: str | None = None


class IncidentToolResult(BaseModel):
    status: IncidentToolStatus
    incidents: list[IncidentRecord] = Field(default_factory=list)
    message: str


def _service_url(configured_url: str | None) -> str | None:
    base_url = (configured_url or os.getenv("INCIDENTS_SERVICE_URL", "")).strip().rstrip("/")
    if not base_url:
        return None
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return base_url


def query_incidents(
    query: IncidentToolInput,
    *,
    bearer_token: str | None,
    configured_url: str | None = None,
    timeout_seconds: float = INCIDENT_TOOL_TIMEOUT_SECONDS,
) -> IncidentToolResult:
    """Query only GET incident endpoints; never logs request details or response bodies."""
    if query.incident_id is not None and not INCIDENT_ID_PATTERN.fullmatch(query.incident_id):
        return IncidentToolResult(
            status=IncidentToolStatus.AMBIGUOUS,
            message="Necesito el ID interno de 12 caracteres hexadecimales para consultar una incidencia.",
        )
    base_url = _service_url(configured_url)
    if base_url is None:
        return IncidentToolResult(
            status=IncidentToolStatus.UNAVAILABLE,
            message="El gestor de incidencias no está disponible en este momento.",
        )
    if not bearer_token:
        return IncidentToolResult(
            status=IncidentToolStatus.PERMISSION_DENIED,
            message="No tengo permisos para consultar el gestor de incidencias.",
        )

    if query.incident_id is not None:
        url = f"{base_url}/api/incidents/{query.incident_id.lower()}"
        params = None
    else:
        url = f"{base_url}/api/incidents"
        params = {
            key: value
            for key, value in {
                "status": query.status,
                "category": query.category,
                "branch": query.branch,
            }.items()
            if value is not None
        }

    try:
        response = httpx.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"},
            timeout=timeout_seconds,
            follow_redirects=False,
        )
    except httpx.TimeoutException:
        return IncidentToolResult(
            status=IncidentToolStatus.TIMEOUT,
            message="La consulta de incidencias excedió el tiempo límite; no pude confirmar los datos.",
        )
    except httpx.HTTPError:
        return IncidentToolResult(
            status=IncidentToolStatus.UNAVAILABLE,
            message="El gestor de incidencias no está disponible en este momento.",
        )

    if response.status_code in {401, 403}:
        return IncidentToolResult(
            status=IncidentToolStatus.PERMISSION_DENIED,
            message="No tengo permisos para consultar el gestor de incidencias.",
        )
    if response.status_code == 404 and query.incident_id is not None:
        return IncidentToolResult(
            status=IncidentToolStatus.NOT_FOUND,
            message="No encontré una incidencia con ese ID en el gestor.",
        )
    if response.status_code < 200 or response.status_code >= 300:
        return IncidentToolResult(
            status=IncidentToolStatus.UNAVAILABLE,
            message="El gestor de incidencias no está disponible en este momento.",
        )

    try:
        payload = response.json()
        raw_incidents = [payload] if query.incident_id is not None else payload
        incidents = [IncidentRecord.model_validate(item) for item in raw_incidents]
    except (ValueError, TypeError):
        return IncidentToolResult(
            status=IncidentToolStatus.UNAVAILABLE,
            message="El gestor de incidencias devolvió una respuesta no válida.",
        )

    return IncidentToolResult(
        status=IncidentToolStatus.SUCCESS,
        incidents=incidents,
        message="Consulta de incidencias completada.",
    )
