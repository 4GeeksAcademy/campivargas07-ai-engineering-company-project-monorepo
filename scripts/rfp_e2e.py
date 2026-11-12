"""Verify RFP intake, generation and human approval against a local demo API."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlsplit

import httpx


def wait_for(fetch, ready, label):
    deadline = monotonic() + 90
    while monotonic() < deadline:
        payload = fetch()
        if payload.get("error_code") or payload.get("approval_status") in {"failed", "agotado", "rechazado"}:
            raise RuntimeError(f"{label}: el procesamiento falló o requiere revisión.")
        if ready(payload):
            return payload
        sleep(0.5)
    raise RuntimeError(f"{label}: se agotó el tiempo de espera.")


def run(api: httpx.Client, pdf: Path, approve: bool) -> None:
    def request(method, path, **kwargs):
        response = api.request(method, path, **kwargs)
        if not response.is_success:
            raise RuntimeError(f"{method} {path} devolvió HTTP {response.status_code}.")
        return response.json()

    with pdf.open("rb") as file:
        ticket = request("POST", "/rfp-requests", files={"file": (pdf.name, file, "application/pdf")})
    path = f"/rfp-requests/{ticket['ticket_id']}"
    status = lambda: request("GET", path)
    wait_for(status, lambda row: row["status"] == "analisis_completo", "Recepción")
    print("Recepción confirmada.")
    request("POST", path + "/generate")
    wait_for(status, lambda row: row["generation_status"] == "completed", "Generación")
    handoff = request("GET", path + "/result")["generation_handoff"]
    if not handoff or not handoff["sections"]:
        raise RuntimeError("El ticket no produjo secciones para revisar.")
    print(f"Generación confirmada, {len(handoff['sections'])} secciones.")
    request("POST", path + "/approval/start")
    wait_for(
        lambda: request("GET", path + "/approvals"),
        lambda row: row["approval_status"] == "esperando_aprobación",
        "Revisión",
    )
    print(f"Ticket {ticket['ticket_id']} listo para revisión en el backoffice.")
    if not approve:
        return

    for section in handoff["sections"]:
        department = section["department_id"]
        request("POST", path + f"/approvals/{department}", json={"decision": "approve", "version": section["version"]})
    if handoff["requires_ceo_approval"]:
        request("POST", path + "/approvals/ceo", json={"decision": "approve"})
    wait_for(status, lambda row: row["status"] == "terminado", "Cierre")
    document = request("GET", path + "/final-document")
    if not document["content"] or not document["sections"]:
        raise RuntimeError("El documento final está vacío.")
    print("Documento final verificado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="PDF con datos sintéticos.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--approve", action="store_true", help="Registrar decisiones en la demo con la cuenta autorizada.")
    args = parser.parse_args()
    target = urlsplit(args.api)
    if target.scheme not in {"http", "https"} or target.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Este script requiere una API local.")
    email = input("Correo de la cuenta de demo: ").strip()
    password = getpass("Contraseña de demo: ")
    try:
        with httpx.Client(base_url=args.api, timeout=20, trust_env=False) as api:
            login = api.post("/auth/login", json={"email": email, "password": password})
            if not login.is_success:
                raise RuntimeError("No se pudo autenticar la cuenta de demo.")
            api.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            run(api, args.pdf, args.approve)
    except (httpx.HTTPError, OSError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
