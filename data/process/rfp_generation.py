"""Parte 2: generación y evaluación de respuestas por departamento (RFPs).

Infraestructura compartida + generadores identificables por departamento.
No copia lógica de negocio desde otras capas; importa transformaciones de
data/process/rfp.py cuando corresponde.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import httpx

from data.process.rfp import DEPARTMENT_LABELS, DEPARTMENTS


class ConfigurationError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


@dataclass
class RfpGenerationSettings:
    generation_url: str
    generation_model: str
    generation_key: str
    timeout: float = 30.0
    max_iterations: int = 3
    fx_rate_usd_cop: Optional[float] = None
    fx_source: str = ""
    competitor_names: list[str] = field(default_factory=list)
    knowledge_enabled: bool = False
    config_source: str = "rfp"


def load_settings() -> RfpGenerationSettings:
    rfp_url = os.getenv("RFP_GENERATION_URL", "").strip()
    rfp_model = os.getenv("RFP_GENERATION_MODEL", "").strip()
    rfp_key = os.getenv("RFP_GENERATION_API_KEY", "").strip()
    rag_url = os.getenv("RAG_GENERATION_URL", "").strip()
    rag_model = os.getenv("RAG_GENERATION_MODEL", "").strip()
    rag_key = os.getenv("RAG_GENERATION_API_KEY", "").strip() or os.getenv("RAG_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    if rfp_url or rfp_model or rfp_key:
        url, model, key = rfp_url, rfp_model, rfp_key
        source = "rfp"
    elif rag_url or rag_model or rag_key:
        url, model, key = rag_url, rag_model, rag_key
        source = "rag_fallback"
    else:
        url, model, key, source = "", "", "", "missing"

    if not url or not model or not key:
        raise ConfigurationError(
            "Falta configuración de generación RFP: defina RFP_GENERATION_URL, "
            "RFP_GENERATION_MODEL y RFP_GENERATION_API_KEY (o RAG_GENERATION_* como fallback)."
        )

    timeout_raw = os.getenv("RFP_GENERATION_TIMEOUT_SECONDS", "30").strip() or "30"
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ConfigurationError("RFP_GENERATION_TIMEOUT_SECONDS inválido") from exc
    if not 0 < timeout <= 120:
        raise ConfigurationError("RFP_GENERATION_TIMEOUT_SECONDS fuera de rango")

    max_iter_raw = os.getenv("RFP_MAX_ITERATIONS", "3").strip() or "3"
    try:
        max_iterations = int(max_iter_raw)
    except ValueError as exc:
        raise ConfigurationError("RFP_MAX_ITERATIONS inválido") from exc
    if max_iterations < 1 or max_iterations > 10:
        raise ConfigurationError("RFP_MAX_ITERATIONS fuera de rango (1-10)")

    fx_raw = os.getenv("RFP_FX_RATE_USD_COP", "").strip()
    fx_rate = None
    fx_source = ""
    if fx_raw:
        try:
            fx_rate = float(fx_raw)
        except ValueError as exc:
            raise ConfigurationError("RFP_FX_RATE_USD_COP inválido") from exc
        if fx_rate <= 0:
            raise ConfigurationError("RFP_FX_RATE_USD_COP debe ser positivo")
        fx_source = "env:RFP_FX_RATE_USD_COP"

    competitors = [x.strip() for x in os.getenv("RFP_COMPETITOR_NAMES", "").split(",") if x.strip()]
    knowledge_enabled = os.getenv("RFP_KNOWLEDGE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}

    return RfpGenerationSettings(
        generation_url=url,
        generation_model=model,
        generation_key=key,
        timeout=timeout,
        max_iterations=max_iterations,
        fx_rate_usd_cop=fx_rate,
        fx_source=fx_source,
        competitor_names=competitors,
        knowledge_enabled=knowledge_enabled,
        config_source=source,
    )


async def _post_json(url: str, key: str, payload: dict, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Expected object")
            return result
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("El proveedor no devolvió una respuesta válida") from exc


def _call_model(settings: RfpGenerationSettings, system_prompt: str, user_payload: dict) -> str:
    import asyncio

    async def _run():
        result = await _post_json(
            settings.generation_url,
            settings.generation_key,
            {
                "model": settings.generation_model,
                "stream": False,
                "tool_choice": "none",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
            },
            settings.timeout,
        )
        try:
            choice = result["choices"][0]
            message = choice["message"]
            answer = message["content"]
            if choice.get("finish_reason") != "stop" or message.get("tool_calls") or message.get("refusal"):
                raise ValueError("Generación incompleta")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Respuesta vacía")
            return answer.strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Contrato de generación inválido") from exc

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Already inside an event loop: run in a new loop via thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _run()).result()


# ---------------- Readability ----------------

@dataclass
class MetricResult:
    metric_name: str
    value: Optional[float]
    available: bool
    limitations_note: str


@dataclass
class ReadabilityResult:
    pass_: Optional[bool]
    score: Optional[float]
    details: str
    metrics: list[MetricResult] = field(default_factory=list)


BASE_READABILITY_LIMITATIONS = (
    "py-readability-metrics está calibrado principalmente para inglés; en español y "
    "textos cortos los índices son informativos y pueden no estar disponibles. "
    "Fragmentos no narrativos (tablas/listas) distorsionan los índices. "
    "Una métrica no disponible no se convierte en 0 ni en aprobación automática."
)


def assess_readability(text: str, language: str = "unknown") -> ReadabilityResult:
    metrics: list[MetricResult] = []
    try:
        from readability import Readability

        r = Readability(text)
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
                metrics.append(MetricResult(name, value, True, BASE_READABILITY_LIMITATIONS))
            except Exception as exc:  # noqa: BLE001
                metrics.append(MetricResult(name, None, False, f"{BASE_READABILITY_LIMITATIONS} (no disponible: {exc})"))
    except Exception as exc:  # noqa: BLE001
        metrics.append(MetricResult("readability_unavailable", None, False, f"{BASE_READABILITY_LIMITATIONS} (librería: {exc})"))

    flesch = next((m.value for m in metrics if m.metric_name == "flesch_reading_ease" and m.available), None)
    if flesch is None:
        pass_ = None
        score = None
        details = "Legibilidad no evaluable: métrica principal no disponible."
    else:
        score = flesch
        pass_ = flesch >= 10.0
        details = f"Flesch Reading Ease={flesch:.2f}; umbral de aprobación=10.00."
    return ReadabilityResult(pass_=pass_, score=score, details=details, metrics=metrics)


# ---------------- Relevance ----------------

@dataclass
class RelevanceResult:
    pass_: bool
    missing_aspects: list[str] = field(default_factory=list)
    details: str = ""


def assess_relevance(department_id: str, draft: str, aspects: list[dict[str, Any]]) -> RelevanceResult:
    if not draft.strip():
        return RelevanceResult(False, [a.get("aspect", "") for a in aspects], "Borrador vacío.")
    missing: list[str] = []
    lowered = draft.lower()
    for item in aspects:
        aspect = str(item.get("aspect", "")).strip()
        if not aspect:
            continue
        keywords = [w for w in re.findall(r"\w{4,}", aspect.lower())]
        if keywords and not any(kw in lowered for kw in keywords):
            missing.append(aspect)
    pass_ = len(missing) == 0 or len(missing) < len(aspects)
    details = "Todos los aspectos relevantes cubiertos." if not missing else f"Aspectos posiblemente ausentes: {', '.join(missing)}."
    return RelevanceResult(pass_=pass_, missing_aspects=missing, details=details)


# ---------------- Compliance ----------------

@dataclass
class ComplianceResult:
    pass_: bool
    rule_ids: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    details: str = ""


PRICE_PATTERN = re.compile(r"\$\s*[\d][\d,.\s]*")
FAST_SETUP_PATTERN = re.compile(r"(\d+)\s*d[ií]as?\s*h[aá]biles?", re.IGNORECASE)


def check_fast_setup(text: str) -> list[str]:
    violations = []
    for match in FAST_SETUP_PATTERN.finditer(text):
        try:
            days = int(match.group(1))
        except ValueError:
            continue
        if days < 10:
            violations.append(f"Promesa de montaje/entrega en {days} días hábiles (<10): '{match.group(0)}'.")
    return violations


def assess_section_compliance(text: str, settings: RfpGenerationSettings) -> ComplianceResult:
    violations: list[str] = []
    rule_ids: list[str] = []

    # RULE_PRICE_CURRENCY
    rule_ids.append("RULE_PRICE_CURRENCY")
    if PRICE_PATTERN.search(text):
        if not ("COP" in text and "USD" in text):
            violations.append("Precio expresado sin ambas monedas (COP y USD).")

    # RULE_NO_FAST_SETUP
    rule_ids.append("RULE_NO_FAST_SETUP")
    violations.extend(check_fast_setup(text))

    # RULE_NO_COMPETITORS
    rule_ids.append("RULE_NO_COMPETITORS")
    lowered = text.lower()
    for name in settings.competitor_names:
        if name.lower() in lowered:
            violations.append(f"Mención de competidor: {name}.")

    pass_ = len(violations) == 0
    details = "Cumplimiento de sección OK." if pass_ else "Violaciones de sección detectadas."
    return ComplianceResult(pass_=pass_, rule_ids=rule_ids, violations=violations, details=details)


PILLARS = {
    "calidad consistente": ["calidad consistente", "consistent quality"],
    "experiencia cálida": ["experiencia cálida", "experiencia calida", "warm experience"],
    "velocidad de servicio": ["velocidad de servicio", "service speed"],
}


def assess_global_compliance(
    sections: dict[str, str],
    estimated_value_usd: Optional[float],
    settings: RfpGenerationSettings,
) -> tuple[ComplianceResult, bool, list[str]]:
    combined = "\n".join(sections.values())
    violations: list[str] = []
    rule_ids: list[str] = []

    rule_ids.append("GLOBAL_BRAND_PILLARS")
    missing_pillars = [p for p, variants in PILLARS.items() if not any(v in combined.lower() for v in variants)]
    if missing_pillars:
        violations.append(f"Pilares de marca ausentes: {', '.join(missing_pillars)}.")

    rule_ids.append("GLOBAL_VALIDITY_30_DAYS")
    if not re.search(r"30\s*d[ií]as", combined, re.IGNORECASE):
        violations.append("Falta período de validez de la oferta (30 días desde su emisión).")

    rule_ids.append("GLOBAL_NO_FAST_SETUP")
    violations.extend(check_fast_setup(combined))

    rule_ids.append("GLOBAL_NO_COMPETITORS")
    lowered = combined.lower()
    for name in settings.competitor_names:
        if name.lower() in lowered:
            violations.append(f"Mención de competidor en la propuesta: {name}.")

    rule_ids.append("GLOBAL_PRICE_CURRENCY")
    # If any price appears globally, both currencies must appear globally.
    if PRICE_PATTERN.search(combined) and not ("COP" in combined and "USD" in combined):
        violations.append("Precio global expresado sin ambas monedas (COP y USD).")

    requires_ceo = None
    if estimated_value_usd is not None:
        requires_ceo = estimated_value_usd > 50000.0
        rule_ids.append("GLOBAL_CEO_THRESHOLD")
        # Not a violation; informational signal.

    pass_ = len(violations) == 0
    details = "Cumplimiento global OK." if pass_ else "Violaciones globales detectadas."
    return ComplianceResult(pass_=pass_, rule_ids=rule_ids, violations=violations, details=details), bool(requires_ceo) if requires_ceo is not None else False, missing_pillars


# ---------------- Evaluation result ----------------

@dataclass
class EvaluationResult:
    section_id: str
    department_id: str
    iteration: int
    readability: dict[str, Any]
    relevance: dict[str, Any]
    compliance: dict[str, Any]
    overall_pass: bool
    feedback_for_generator: str


def evaluate_section(
    department_id: str,
    draft: str,
    aspects: list[dict[str, Any]],
    iteration: int,
    settings: RfpGenerationSettings,
) -> EvaluationResult:
    readability = assess_readability(draft)
    relevance = assess_relevance(department_id, draft, aspects)
    compliance = assess_section_compliance(draft, settings)

    overall = (
        (readability.pass_ is True)
        and relevance.pass_
        and compliance.pass_
    )

    feedback_parts = []
    if readability.pass_ is not True:
        feedback_parts.append(f"Legibilidad: {readability.details}")
    if not relevance.pass_:
        feedback_parts.append(f"Pertinencia: {relevance.details} Faltan: {', '.join(relevance.missing_aspects)}.")
    if not compliance.pass_:
        feedback_parts.append(f"Cumplimiento: {'; '.join(compliance.violations)}")
    feedback = " ".join(feedback_parts).strip() or "Sin observaciones."

    return EvaluationResult(
        section_id=department_id,
        department_id=department_id,
        iteration=iteration,
        readability=asdict(readability),
        relevance=asdict(relevance),
        compliance=asdict(compliance),
        overall_pass=overall,
        feedback_for_generator=feedback,
    )


# ---------------- Generators ----------------

GENERATOR_INSTRUCTIONS: dict[str, str] = {
    "marketing": (
        "Eres el generador de la sección de Marketing y Experiencia Digital para una propuesta RFP de Brasaland. "
        "Incluye términos de marca, exclusividad, co-branding, validez de la oferta (30 días desde emisión), "
        "y los tres pilares de marca cuando corresponda. No inventes precios ni cifras no presentes en los metadatos."
    ),
    "operaciones": (
        "Eres el generador de la sección de Operaciones de Restaurante. Cubre viabilidad operativa, capacidad de cocina/personal, "
        "tiempos de montaje y costo operativo por evento. Ningún montaje/entrega menor a 10 días hábiles. No inventes capacidad."
    ),
    "procurement": (
        "Eres el generador de la sección de Procurement y Proveedores. Cubre costo estimado de insumos según volumen y tiempos de entrega. "
        "Todo precio en COP y USD. No inventes precios, volúmenes ni disponibilidad."
    ),
    "training": (
        "Eres el generador de la sección de Training y Estándares de Calidad. Cubre si se requiere receta/estándar nuevo, "
        "tiempo de desarrollo y certificación. No inventes certificaciones ni plazos."
    ),
}


def _generator_id(department_id: str) -> str:
    return f"{department_id}-section-generator"


def generate_section(
    department_id: str,
    metadata: dict[str, Any],
    aspects: list[dict[str, Any]],
    settings: RfpGenerationSettings,
    feedback: Optional[str] = None,
    client: Any = None,
) -> str:
    if department_id not in GENERATOR_INSTRUCTIONS:
        raise ValueError(f"Generador no registrado para departamento: {department_id}")

    open_questions = []
    if not metadata.get("budget_range"):
        open_questions.append("Presupuesto no especificado en la RFP")
    if not metadata.get("scope"):
        open_questions.append("Alcance/volumen no definido")

    system_prompt = (
        GENERATOR_INSTRUCTIONS[department_id]
        + "\n\nReglas globales: todo precio en COP y USD; ninguna entrega/montaje <10 días hábiles; "
        "sin nombres de competidores; validez de la oferta 30 días desde su emisión; no inventar cifras. "
        "Registra cifras faltantes en open_questions. Devuelve solo el texto de la sección."
    )
    user_payload = {
        "department": department_id,
        "department_label": DEPARTMENT_LABELS.get(department_id, department_id),
        "metadata": metadata,
        "key_aspects": aspects,
        "previous_feedback": feedback,
        "open_questions": open_questions,
        "fx_rate_usd_cop": settings.fx_rate_usd_cop,
        "fx_source": settings.fx_source,
    }

    text = _call_model(settings, system_prompt, user_payload)
    if feedback:
        text = text + "\n\n[Corregido según feedback del evaluador]"
    return text


def generate_sections_parallel(
    departments: list[str],
    metadata: dict[str, Any],
    aspects_by_department: dict[str, list[dict[str, Any]]],
    settings: RfpGenerationSettings,
    feedback_by_department: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    feedback_by_department = feedback_by_department or {}

    def _run_one(dept: str) -> tuple[str, str]:
        return dept, generate_section(
            dept,
            metadata,
            aspects_by_department.get(dept, []),
            settings,
            feedback=feedback_by_department.get(dept),
        )

    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(departments))) as pool:
        for dept, content in pool.map(lambda d: _run_one(d), departments):
            results[dept] = content
    return results


def estimate_value_usd(metadata: dict[str, Any]) -> Optional[float]:
    budget = str(metadata.get("budget_range", "") or "")
    match = re.search(r"([\d][\d,\.]*)", budget)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if "k" in budget.lower():
        value *= 1000
    return value


def prompt_hash(department_id: str, metadata: dict[str, Any], feedback: Optional[str]) -> str:
    payload = json.dumps({"department": department_id, "metadata": metadata, "feedback": feedback}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()