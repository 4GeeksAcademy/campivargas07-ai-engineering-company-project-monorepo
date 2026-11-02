"""Deterministic tests for RFP response generation (Parte 2)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from data.process.rfp_generation import (
    EvaluationResult,
    assess_global_compliance,
    assess_section_compliance,
    evaluate_section,
    load_settings,
)


def _settings():
    os.environ.update(
        {
            "RFP_GENERATION_URL": "https://example.com/v1/chat/completions",
            "RFP_GENERATION_MODEL": "test-model",
            "RFP_GENERATION_API_KEY": "test-key",
            "RFP_MAX_ITERATIONS": "2",
        }
    )
    return load_settings()


def test_section_compliance_rejects_fast_setup():
    settings = _settings()
    result = assess_section_compliance("Entrega en 5 días hábiles.", settings)
    assert result.pass_ is False
    assert any("días hábiles" in v for v in result.violations)


def test_section_compliance_requires_both_currencies_when_price_present():
    settings = _settings()
    result = assess_section_compliance("Precio: $1000 USD.", settings)
    assert result.pass_ is False
    assert any("ambas monedas" in v for v in result.violations)


def test_global_compliance_requires_pillars_and_validity():
    settings = _settings()
    sections = {"marketing": "Propuesta con calidad consistente y experiencia cálida."}
    result, requires_ceo, _ = assess_global_compliance(sections, 10000.0, settings)
    assert result.pass_ is False
    assert any("Pilares de marca ausentes" in v for v in result.violations)
    assert any("validez" in v.lower() for v in result.violations)


def test_global_compliance_passes_when_all_rules_present():
    settings = _settings()
    text = (
        "Calidad consistente, experiencia cálida y velocidad de servicio. "
        "Validez de la oferta: 30 días desde su emisión. Precio: 1000 COP y 1 USD."
    )
    sections = {"marketing": text}
    result, requires_ceo, _ = assess_global_compliance(sections, 10000.0, settings)
    assert result.pass_ is True
    assert requires_ceo is False


def test_global_compliance_ceo_threshold():
    settings = _settings()
    text = (
        "Calidad consistente, experiencia cálida y velocidad de servicio. "
        "Validez de la oferta: 30 días desde su emisión."
    )
    sections = {"marketing": text}
    _, requires_ceo, _ = assess_global_compliance(sections, 60000.0, settings)
    assert requires_ceo is True


def test_evaluate_section_passes_with_good_draft():
    settings = _settings()
    draft = (
        "Esta es una seccion de marketing. " * 20
        + "Calidad consistente, experiencia calida y velocidad de servicio. "
        + "Validez de la oferta: 30 dias desde su emision. Precio: 1000 COP y 1 USD. "
        + "Términos de marca."
    )
    result = evaluate_section("marketing", draft, [{"aspect": "Términos de marca"}], 1, settings)
    assert isinstance(result, EvaluationResult)
    assert result.overall_pass is True
    assert result.feedback_for_generator == "Sin observaciones."


def test_evaluate_section_fails_fast_setup():
    settings = _settings()
    draft = "Entrega en 5 días hábiles. Precio: 1000 COP y 1 USD."
    result = evaluate_section("operaciones", draft, [], 1, settings)
    assert result.overall_pass is False
    assert "Cumplimiento" in result.feedback_for_generator


def test_pipeline_approved_and_failed_paths(monkeypatch):
    os.environ.update(
        {
            "RFP_GENERATION_URL": "https://example.com/v1/chat/completions",
            "RFP_GENERATION_MODEL": "test-model",
            "RFP_GENERATION_API_KEY": "test-key",
            "RFP_MAX_ITERATIONS": "2",
        }
    )

    from data.pipelines.rfp_response_generation import run_rfp_response_generation
    import data.process.rfp_generation as gen

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        if department_id == "operaciones":
            # First attempt fails (<10 days), second passes.
            if feedback:
                return "Entrega en 12 dias habiles. " + ("Esta es una frase simple. " * 30) + "Precio: 1000 COP y 1 USD. Viabilidad operativa."
            return "Entrega en 5 dias habiles. " + ("Esta es una frase simple. " * 30) + "Precio: 1000 COP y 1 USD. Viabilidad operativa."
        return "Esta es una seccion de marketing. " * 20 + "Calidad consistente, experiencia calida y velocidad de servicio. Validez de la oferta: 30 dias desde su emision. Precio: 1000 COP y 1 USD. Términos de marca."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)

    result = run_rfp_response_generation(
        ticket_id="t1",
        active_departments=["marketing", "operaciones"],
        metadata={"client_name": "X", "scope": "Y"},
        aspects_by_department={"marketing": [{"aspect": "Términos"}], "operaciones": [{"aspect": "Viabilidad"}]},
        max_iterations=2,
    )

    assert result["error_code"] is None
    assert result["approved"]["marketing"] is True
    assert result["approved"]["operaciones"] is True
    assert result["draft_iterations"]["operaciones"] == 2
    assert result["outcome"] == "generacion_completa"


def test_pipeline_exhausts_iteration_limit(monkeypatch):
    os.environ.update(
        {
            "RFP_GENERATION_URL": "https://example.com/v1/chat/completions",
            "RFP_GENERATION_MODEL": "test-model",
            "RFP_GENERATION_API_KEY": "test-key",
            "RFP_MAX_ITERATIONS": "1",
        }
    )

    from data.pipelines.rfp_response_generation import run_rfp_response_generation
    import data.process.rfp_generation as gen

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        return "Entrega en 5 dias habiles. " + ("Esta es una frase simple. " * 30) + "Precio: 1000 COP y 1 USD."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)

    result = run_rfp_response_generation(
        ticket_id="t2",
        active_departments=["operaciones"],
        metadata={},
        aspects_by_department={"operaciones": []},
        max_iterations=1,
    )

    assert result["approved"]["operaciones"] is False
    assert result["outcome"] == "needs_human_review"
    assert "operaciones" in result["exhausted"]


def test_pipeline_isolation_between_departments(monkeypatch):
    os.environ.update(
        {
            "RFP_GENERATION_URL": "https://example.com/v1/chat/completions",
            "RFP_GENERATION_MODEL": "test-model",
            "RFP_GENERATION_API_KEY": "test-key",
            "RFP_MAX_ITERATIONS": "1",
        }
    )

    from data.pipelines.rfp_response_generation import run_rfp_response_generation
    import data.process.rfp_generation as gen

    calls = {"deps": []}

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        calls["deps"].append(department_id)
        return "Calidad consistente, experiencia cálida y velocidad de servicio. Validez de la oferta: 30 días desde su emisión. Precio: 1000 COP y 1 USD."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)

    result = run_rfp_response_generation(
        ticket_id="t3",
        active_departments=["marketing"],
        metadata={},
        aspects_by_department={},
        max_iterations=1,
    )

    assert result["drafts"].keys() == {"marketing"}
    assert result["evaluations"].keys() == {"marketing"}
    assert calls["deps"] == ["marketing"]


def test_configuration_error_when_missing_settings(monkeypatch):
    for key in ("RFP_GENERATION_URL", "RFP_GENERATION_MODEL", "RFP_GENERATION_API_KEY", "RAG_GENERATION_URL", "RAG_GENERATION_MODEL", "RAG_GENERATION_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    from data.process.rfp_generation import load_settings

    with pytest.raises(Exception):
        load_settings()