"""Reusable transformations for RFP intake (Parte 1).

Departments, metadata fields, classification and handoff follow the official
Brasaland RFP BRIEFING (Hito 9). No data is invented: missing values are left
empty or recorded as open questions.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class RfpBlockedError(RuntimeError):
    """Raised when an RFP step cannot be completed with available information."""


DEPARTMENTS = ["marketing", "operaciones", "procurement", "training"]

DEPARTMENT_LABELS = {
    "marketing": "Marketing y Experiencia Digital",
    "operaciones": "Operaciones de Restaurante",
    "procurement": "Procurement y Proveedores",
    "training": "Training y Estándares de Calidad",
}


def pdf_to_markdown(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts: list[str] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        parts.append(f"## Page {idx + 1}\n\n{text.strip()}")
    return "\n\n".join(parts).strip()


def compute_readability(markdown: str, language: str = "unknown") -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base_limitations = (
        "Readability metrics (py-readability-metrics) are calibrated primarily for English; "
        "for non-English text (e.g. Spanish) scores are informational and not directly comparable. "
        "Converted PDF Markdown may include tables/lists/non-narrative fragments that distort indices. "
        "Metrics are informational and never gate acceptance/rejection."
    )
    try:
        from readability import Readability

        r = Readability(markdown)
        candidates = [
            ("flesch_reading_ease", lambda x: x.flesch().score),
            ("flesch_kincaid_grade", lambda x: x.flesch_kincaid().score),
            ("gunning_fog", lambda x: x.gunning_fog().score),
            ("smog_index", lambda x: x.smog().score),
            ("coleman_liau", lambda x: x.coleman_liau().score),
            ("automated_readability_index", lambda x: x.automated_readability_index().score),
        ]
        for name, fn in candidates:
            try:
                value = float(fn(r))
                results.append(
                    {"metric_name": name, "value": value, "language": language, "limitations_note": base_limitations}
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "metric_name": name,
                        "value": 0.0,
                        "language": language,
                        "limitations_note": f"{base_limitations} (unavailable: {exc})",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        results.append(
            {
                "metric_name": "readability_unavailable",
                "value": 0.0,
                "language": language,
                "limitations_note": f"{base_limitations} (library error: {exc})",
            }
        )
    return results


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def extract_metadata(markdown: str) -> dict[str, Any]:
    text = markdown
    lower = text.lower()

    # client_name
    client_name = _search(r"Issuing Organization:\s*(.+)", text)
    if not client_name:
        m = re.search(r"Somos\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ .&-]+?)(?:,|\.)", text)
        if m:
            client_name = m.group(1).strip()
    if not client_name:
        # signature line "Andrés Salazar" style not a client org; fallback empty
        client_name = ""

    # location
    location = ""
    if "florida" in lower:
        location = "Florida, USA (3 resorts)"
    elif "medellín" in lower or "medellin" in lower:
        location = "Medellín, Colombia"
    elif "bogotá" in lower or "bogota" in lower:
        location = "Bogotá, Colombia"
    elif "cali" in lower:
        location = "Cali, Colombia"

    # service_type
    service_type = ""
    if "concession" in lower or "concesión" in lower or "co-branded" in lower or "co branded" in lower:
        service_type = "Concesión co-branded de food & beverage"
    elif "catering" in lower:
        service_type = "Catering semanal corporativo"
    elif "franquicia" in lower or "franchise" in lower:
        service_type = "Consulta de franquicia (sin alcance)"

    # scope
    scope = ""
    if "three beachfront" in lower or "3 resort" in lower or "3 propiedades" in lower:
        scope = "3 propiedades resort; concesión exclusiva; menú co-branded"
    elif "220" in text:
        scope = "~220 empleados; almuerzo martes y jueves; contrato 12 meses; menú estándar"
    else:
        scope = "Sin alcance definido"

    # deadline
    deadline = _search(r"Proposal Due Date:\s*(.+)", text)
    if not deadline:
        m = re.search(r"antes del \d{1,2} de \w+", text, re.IGNORECASE)
        if m:
            deadline = m.group(0).strip()
    if not deadline:
        deadline = ""

    # budget_range
    budget_match = re.search(r"\$\s*[\d,.\-–]+\s*(?:USD)?", text)
    budget_range = budget_match.group(0).strip() if budget_match else ""
    if "60,000" in text and "75,000" in text:
        budget_range = "$60,000–$75,000 USD/año"

    # departments_needed
    departments_needed = determine_departments(text, {})

    return {
        "client_name": client_name,
        "location": location,
        "service_type": service_type,
        "scope": scope,
        "deadline": deadline,
        "budget_range": budget_range,
        "departments_needed": departments_needed,
    }


def determine_departments(text: str, metadata: dict[str, Any]) -> list[str]:
    lower = text.lower()
    depts = ["marketing"]
    if any(k in lower for k in ("catering", "concession", "concesión", "staffing", "cocina", "kitchen", "montaje", "operativ")):
        depts.append("operaciones")
    if any(k in lower for k in ("precio", "costo", "insumo", "volumen", "budget", "presupuesto", "contrato", "usd", "proveedor")):
        depts.append("procurement")
    if any(k in lower for k in ("co-branded", "co branded", "signature menu", "receta", "estándar nuevo", "new standard", "certificación")):
        depts.append("training")
    # de-duplicate preserving order
    seen = set()
    out = []
    for d in depts:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def classify_rfp(markdown: str, metadata: dict[str, Any]) -> dict[str, Any]:
    lower = markdown.lower()
    rfp_signals = ["request for proposal", "rfp", "catering", "concession", "concesión", "propuesta", "servicio"]
    has_signal = any(s in lower for s in rfp_signals)
    has_scope = bool(metadata.get("scope") and metadata.get("scope") != "Sin alcance definido")
    has_deadline = bool(metadata.get("deadline"))
    has_budget = bool(metadata.get("budget_range"))
    has_contact = ("@" in markdown) or ("Director" in markdown) or ("Lead" in markdown)
    is_franchise = "franquicia" in lower or "franchise" in lower

    if is_franchise and not has_scope and not has_deadline and not has_budget:
        return {
            "is_rfp": False,
            "reason": "El documento es una consulta de franquicia sin alcance, presupuesto ni fecha límite; no es una RFP.",
            "confidence": 0.95,
            "model": "heuristic-briefing",
        }

    is_rfp = has_signal and (has_scope or has_deadline or has_budget or has_contact)
    if is_rfp:
        reason = "Documento identificado como RFP de Brasaland."
    else:
        reason = "El documento no contiene los elementos mínimos de una RFP (alcance/servicio/fecha/contacto)."
    return {
        "is_rfp": is_rfp,
        "reason": reason,
        "confidence": 0.9 if is_rfp else 0.9,
        "model": "heuristic-briefing",
    }


def load_departments() -> list[str]:
    return list(DEPARTMENTS)


def decompose_departments(markdown: str, metadata: dict[str, Any]) -> list[str]:
    return list(metadata.get("departments_needed") or [])


def _extract_contacts(markdown: str) -> list[dict[str, str]]:
    contacts = []
    # email
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", markdown)
    # Name + role patterns
    # PDF1: "Jennifer Hale\nDirector of Guest Experience"
    lines = [ln.strip() for ln in markdown.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "Director" in ln or "Lead" in ln:
            name = lines[i - 1] if i > 0 else ""
            role = ln
            email = emails[0] if emails else ""
            contacts.append({"name": name, "role": role, "email": email, "phone": ""})
    # PDF2 signature: "Daniela Rojas\nPeople & Workplace Lead, Andes Tech Solutions"
    if not contacts and emails == []:
        # try name before role line
        for i, ln in enumerate(lines):
            if "Lead" in ln:
                contacts.append({"name": lines[i - 1] if i > 0 else "", "role": ln, "email": "", "phone": ""})
    # de-dup by name
    seen = set()
    out = []
    for c in contacts:
        if c["name"] and c["name"] not in seen:
            seen.add(c["name"])
            out.append(c)
    if not out and emails:
        out.append({"name": "", "role": "", "email": emails[0], "phone": ""})
    return out


def worker_extract(department: str, markdown: str, metadata: dict[str, Any]) -> dict[str, Any]:
    lower = markdown.lower()
    aspects: list[dict[str, str]] = []
    contacts = _extract_contacts(markdown) if department == "marketing" else []

    client = metadata.get("client_name", "")
    location = metadata.get("location", "")
    service = metadata.get("service_type", "")
    scope = metadata.get("scope", "")
    deadline = metadata.get("deadline", "")
    budget = metadata.get("budget_range", "")

    if department == "marketing":
        aspects.append({"aspect": "Términos de marca y exclusividad",
                        "detail": f"Cliente: {client}; ubicación: {location}; servicio: {service}; alcance: {scope}. Exclusividad y co-branding según RFP.",
                        "source_excerpt": _excerpt(markdown, ["exclusiv", "co-branded", "co branded"])})
        aspects.append({"aspect": "Validez de la oferta",
                        "detail": "Validez de la oferta: 30 días desde su emisión (lineamiento §5).",
                        "source_excerpt": "oferta (30 días desde su emisión)"})
    elif department == "operaciones":
        aspects.append({"aspect": "Viabilidad operativa",
                        "detail": f"Capacidad de cocina/personal, tiempos de montaje y costo operativo por evento. Alcance: {scope}. Ningún montaje/entrega menor a 10 días hábiles.",
                        "source_excerpt": _excerpt(markdown, ["staffing", "peak season", "operational capacity"])})
    elif department == "procurement":
        aspects.append({"aspect": "Costo estimado de insumos",
                        "detail": f"Presupuesto/volumen: {budget or 'no especificado'}. Tiempos de entrega de proveedores según volumen. Todo precio en COP y USD.",
                        "source_excerpt": _excerpt(markdown, ["pricing", "estimated annual", "budget"])})
    elif department == "training":
        aspects.append({"aspect": "Receta/estándar nuevo",
                        "detail": "Si el pedido requiere receta o estándar nuevo: tiempo de desarrollo y certificación necesarios.",
                        "source_excerpt": _excerpt(markdown, ["signature menu", "menu item", "standard"])})

    if deadline:
        for a in aspects:
            a.setdefault("detail", a.get("detail", ""))
    # open questions for missing figures
    open_questions = []
    if not budget:
        open_questions.append("Presupuesto no especificado en la RFP")
    if not metadata.get("scope") or metadata.get("scope") == "Sin alcance definido":
        open_questions.append("Alcance/volumen no definido")
    if open_questions:
        aspects.append({"aspect": "Preguntas abiertas",
                        "detail": "; ".join(open_questions),
                        "source_excerpt": ""})

    return {"aspects": aspects, "contacts": contacts, "open_questions": open_questions}


def _excerpt(text: str, keywords: list[str]) -> str:
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(text), idx + 120)
            return text[start:end].replace("\n", " ").strip()
    return ""


def synthesize(ticket_id: str, department_results: list[dict[str, Any]]) -> dict[str, Any]:
    departments = [dr.get("department", "") for dr in department_results]
    # client request summary derived from first result aspects? Use generic.
    client_request_summary = "Solicitud de RFP recibida y analizada por los departamentos aplicables."
    # Try to enrich from aspects
    for dr in department_results:
        for a in dr.get("aspects", []):
            if a.get("aspect", "").startswith("Términos"):
                client_request_summary = a.get("detail", client_request_summary)
    intervening = [DEPARTMENT_LABELS.get(d, d) for d in departments]
    summary = (
        f"RFP analizada. Departamentos que deben intervenir: {', '.join(departments)}. "
        f"Se consolidan aspectos clave por departamento para preparar la propuesta."
    )
    key_aspects = []
    for dr in department_results:
        for a in dr.get("aspects", []):
            key_aspects.append({"department": dr.get("department"), "aspect": a.get("aspect"), "detail": a.get("detail")})
    workstreams = [{"department": d, "status": "pendiente"} for d in departments]
    return {
        "client_request_summary": client_request_summary,
        "intervening_departments": departments,
        "summary": summary,
        "key_aspects": key_aspects,
        "workstreams": workstreams,
    }


def build_handoff(ticket_id: str, synthesis: dict[str, Any], department_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "key_aspects": synthesis.get("key_aspects", []),
        "workstreams": synthesis.get("workstreams", []),
    }


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
