"""Tests for RFP intake Parte 1."""
from __future__ import annotations

import io
import uuid

import pytest
from pypdf import PdfWriter
from fastapi.testclient import TestClient


def _make_pdf_bytes(text: str = "Sample RFP content") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_create_rfp_returns_202_and_ticket_id(client: TestClient, auth_headers: dict):
    pdf = _make_pdf_bytes()
    files = {"file": ("sample.pdf", pdf, "application/pdf")}
    res = client.post("/rfp-requests", headers=auth_headers, files=files)
    assert res.status_code == 202
    data = res.json()
    assert "ticket_id" in data
    assert data["status"] == "analizando"


def test_get_rfp_status_after_create(client: TestClient, auth_headers: dict):
    pdf = _make_pdf_bytes()
    files = {"file": ("sample.pdf", pdf, "application/pdf")}
    created = client.post("/rfp-requests", headers=auth_headers, files=files).json()
    ticket_id = created["ticket_id"]
    res = client.get(f"/rfp-requests/{ticket_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == ticket_id
    assert data["status"] in ("analizando", "descartado", "analisis_completo")


def test_get_rfp_result_endpoint(client: TestClient, auth_headers: dict):
    pdf = _make_pdf_bytes()
    files = {"file": ("sample.pdf", pdf, "application/pdf")}
    created = client.post("/rfp-requests", headers=auth_headers, files=files).json()
    ticket_id = created["ticket_id"]
    res = client.get(f"/rfp-requests/{ticket_id}/result", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == ticket_id


def test_get_unknown_ticket_404(client: TestClient, auth_headers: dict):
    res = client.get(f"/rfp-requests/{uuid.uuid4()}", headers=auth_headers)
    assert res.status_code == 404
