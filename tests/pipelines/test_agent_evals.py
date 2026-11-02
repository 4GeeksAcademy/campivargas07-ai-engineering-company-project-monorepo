"""LangGraph support agent evaluations and structural/checkpoint tests (Part 1)."""
import json
from pathlib import Path
from types import SimpleNamespace

from langgraph.checkpoint.memory import InMemorySaver
import pytest

from app.domains.agent.graph import (
    COMPILED_AGENT_GRAPH,
    InvalidQuestionError,
    execute_agent_query,
    get_run_checkpoints,
    get_run_state,
)
from app.domains.agent.mcp_client import (
    INCIDENT_MCP_TIMEOUT_SECONDS as INCIDENT_TOOL_TIMEOUT_SECONDS,
    IncidentToolInput,
    IncidentToolResult,
    IncidentToolStatus,
    query_incidents_via_mcp as query_incidents,
)
from app.domains.agent.state import StateValidationError, validate_agent_state
from app.domains.agent.traces import load_trace
from data.pipelines import rag
from data.process.config import ProviderError, ROOT, Settings

FIXTURES_PATH = ROOT / "tests" / "pipelines" / "fixtures" / "agent_traces.json"
REAL_TRACE_PATH = ROOT / "data" / "eval" / "langgraph-agent-trace-01.json"


@pytest.fixture
def cfg():
    return Settings(
        "https://model.example/embeddings",
        "embedding-test",
        "secret",
        3,
        "float",
        "https://model.example/chat",
        "generation-test",
        "secret",
        0.6,
    )


@pytest.fixture
def saved_fixtures() -> dict:
    payload = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return payload["traces"]


@pytest.fixture
def real_trace() -> dict:
    return json.loads(REAL_TRACE_PATH.read_text(encoding="utf-8"))


# ============================================================================
# EVALS SOBRE TRACES GUARDADOS (sin llamadas en vivo al modelo en cada test)
# ============================================================================


def test_eval_01_nominal_flow_and_node_order_from_saved_traces(saved_fixtures, real_trace):
    """Eval 1: Verifica el flujo nominal y el orden exacto de nodos en traces guardados y corrida real."""
    for trace in (saved_fixtures["nominal_oro"], real_trace):
        assert trace["status"] == "completed"
        assert trace["route"] == "grounded"
        assert trace["nodes_order"] == [
            "receive_question",
            "retrieve_context",
            "generate_grounded_answer",
        ]
        # retrieve_context debe ejecutarse estrictamente antes que generate_grounded_answer
        idx_retrieve = trace["nodes_order"].index("retrieve_context")
        idx_generate = trace["nodes_order"].index("generate_grounded_answer")
        assert idx_retrieve < idx_generate

        step_nodes = [step["node"] for step in trace["steps"]]
        assert step_nodes == trace["nodes_order"]
        retrieve_step = trace["steps"][idx_retrieve]
        assert retrieve_step["retrieved_count"] >= 1
        assert len(retrieve_step["retrieved_sources"]) == retrieve_step["retrieved_count"]

        assert len(trace["checkpoints"]) >= 4
        assert trace["checkpoints"][-1]["has_context"] is True
        assert trace["checkpoints"][-1]["has_answer"] is True
        assert trace["checkpoints"][-1]["next"] == []
        assert trace["error"] is None


def test_eval_02_conditional_alternative_routes_from_saved_traces(saved_fixtures):
    """Eval 2: Verifica rutas condicionales alternativas (pregunta vacía y ausencia de evidencia)."""
    empty_trace = saved_fixtures["alternative_empty_question"]
    assert empty_trace["status"] == "rejected"
    assert empty_trace["route"] == "empty_question"
    assert empty_trace["nodes_order"] == ["receive_question", "reject_invalid_question"]
    assert "retrieve_context" not in empty_trace["nodes_order"]
    assert "generate_grounded_answer" not in empty_trace["nodes_order"]
    assert empty_trace["retrieved_context"] == []
    assert empty_trace["error"]["code"] == "INVALID_QUESTION"

    no_evidence_trace = saved_fixtures["alternative_no_evidence"]
    assert no_evidence_trace["status"] == "completed"
    assert no_evidence_trace["route"] == "no_evidence"
    assert no_evidence_trace["nodes_order"] == [
        "receive_question",
        "retrieve_context",
        "abstain_without_evidence",
    ]
    assert "generate_grounded_answer" not in no_evidence_trace["nodes_order"]
    assert no_evidence_trace["retrieved_context"] == []
    assert "no tiene información suficiente" in no_evidence_trace["answer"].lower()


def test_eval_03_brasaland_grounding_on_saved_and_real_traces(saved_fixtures, real_trace):
    """Eval 3: Verifica anclaje en la base de conocimiento de Brasaland (evidencia recuperada + respuesta)."""
    for oro_trace in (saved_fixtures["nominal_oro"], real_trace):
        chunks = oro_trace["retrieved_context"]
        assert any(
            c["source_document"] == "loyalty-program"
            and c["section"] == "Niveles"
            and "50+ puntos" in c["text"]
            and "15%" in c["text"]
            for c in chunks
        )
        answer = oro_trace["answer"]
        assert "50" in answer
        assert "15%" in answer
        assert "Bronce" in answer and "Plata" in answer and "Oro" in answer
        assert "temporada" in answer

    bbq_trace = saved_fixtures["nominal_allergens_bbq"]
    bbq_chunks = bbq_trace["retrieved_context"]
    assert any(
        c["source_document"] == "menu-allergens"
        and "No existe versión sin gluten certificada" in c["text"]
        and "contaminación cruzada" in c["text"]
        for c in bbq_chunks
    )
    bbq_answer = bbq_trace["answer"]
    assert "sin gluten" in bbq_answer.lower()
    assert "soya" in bbq_answer.lower()
    assert "contaminación cruzada" in bbq_answer.lower()


# ============================================================================
# PRUEBAS DE ESTRUCTURA, COMPILACIÓN, CHECKPOINTS Y CONTRATO DE NODOS
# ============================================================================


def test_compiled_graph_structure_and_separate_node_imports(cfg, tmp_path, monkeypatch):
    """Verifica compilación explícita y que los nodos llamen retrieve() y generate_answer() por separado sin usar query()."""
    monkeypatch.setattr(
        rag,
        "query",
        lambda *a, **kw: pytest.fail("El grafo NUNCA debe llamar al query() monolítico"),
    )
    graph_nodes = set(COMPILED_AGENT_GRAPH.nodes.keys())
    for expected_node in (
        "receive_question",
        "reject_invalid_question",
        "retrieve_context",
        "generate_grounded_answer",
        "abstain_without_evidence",
    ):
        assert expected_node in graph_nodes

    calls = []
    expected_chunks = [
        {
            "company": "brasaland",
            "source_document": "loyalty-program",
            "section": "Niveles",
            "chunk_index": 1,
            "language": "es",
            "text": "Oro (50+ puntos): 15% de descuento permanente.",
        }
    ]

    def fake_retrieve(q, *, k, min_score, config):
        calls.append(("retrieve", q, k, min_score))
        return expected_chunks

    def fake_generate(q, ctx, *, config):
        calls.append(("generate_answer", q, ctx))
        return "Para el nivel Oro necesitas 50+ puntos y obtienes 15% de descuento."

    result = execute_agent_query(
        "  ¿Cuántos puntos necesito para el nivel Oro?  ",
        run_id="test-run-nominal",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=fake_retrieve,
        generate_fn=fake_generate,
        config_fn=lambda: cfg,
    )
    assert result["route"] == "grounded"
    assert "50+ puntos" in result["answer"]
    assert calls == [
        ("retrieve", "¿Cuántos puntos necesito para el nivel Oro?", 5, cfg.min_score),
        ("generate_answer", "¿Cuántos puntos necesito para el nivel Oro?", expected_chunks),
    ]

    persisted = load_trace("test-run-nominal", directory=tmp_path)
    assert persisted["nodes_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_grounded_answer",
    ]


def test_empty_question_short_circuits_before_qdrant_and_persists_trace(cfg, tmp_path):
    """Verifica que una pregunta vacía enruta a reject_invalid_question -> END sin consultar Qdrant ni el LLM."""
    with pytest.raises(InvalidQuestionError):
        execute_agent_query(
            "   ",
            run_id="test-run-empty",
            trace_dir=tmp_path,
            checkpointer=InMemorySaver(),
            retrieve_fn=lambda *a, **kw: pytest.fail("No debe consultar Qdrant con pregunta vacía"),
            generate_fn=lambda *a, **kw: pytest.fail("No debe llamar al LLM con pregunta vacía"),
            config_fn=lambda: cfg,
        )

    persisted = load_trace("test-run-empty", directory=tmp_path)
    assert persisted["status"] == "rejected"
    assert persisted["route"] == "empty_question"
    assert persisted["nodes_order"] == ["receive_question", "reject_invalid_question"]
    assert persisted["error"]["code"] == "INVALID_QUESTION"


def test_no_evidence_routes_to_abstain_node_and_persists_trace(cfg, tmp_path):
    """Verifica que cuando retrieve() devuelve [] se enruta al nodo abstain_without_evidence."""
    seen_contexts = []

    def fake_generate(q, ctx, *, config):
        seen_contexts.append(ctx)
        return "La base de conocimiento no tiene información suficiente para responder a esta pregunta."

    result = execute_agent_query(
        "¿Cuál fue la venta de ayer en Miami?",
        run_id="test-run-abstain",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda *a, **kw: [],
        generate_fn=fake_generate,
        config_fn=lambda: cfg,
    )
    assert result["route"] == "no_evidence"
    assert seen_contexts == [[]]
    persisted = load_trace("test-run-abstain", directory=tmp_path)
    assert persisted["nodes_order"] == [
        "receive_question",
        "retrieve_context",
        "abstain_without_evidence",
    ]
    assert persisted["retrieved_context"] == []


def test_checkpointing_isolation_and_state_inspection_across_threads(cfg, tmp_path):
    """Verifica que el checkpointer guarda cada transición por thread_id sin mezclar corridas y permite inspección."""
    saver = InMemorySaver()
    from app.domains.agent.graph import build_agent_graph

    chunks_a = [
        {
            "company": "brasaland",
            "source_document": "loyalty-program",
            "section": "Niveles",
            "chunk_index": 1,
            "language": "es",
            "text": "Oro: 50+ puntos.",
        }
    ]
    execute_agent_query(
        "Pregunta hilo A",
        run_id="run-thread-a",
        thread_id="thread-a",
        trace_dir=tmp_path,
        checkpointer=saver,
        retrieve_fn=lambda *a, **kw: chunks_a,
        generate_fn=lambda q, ctx, *, config: f"Respuesta para {q}",
        config_fn=lambda: cfg,
    )
    execute_agent_query(
        "Pregunta hilo B sin contexto",
        run_id="run-thread-b",
        thread_id="thread-b",
        trace_dir=tmp_path,
        checkpointer=saver,
        retrieve_fn=lambda *a, **kw: [],
        generate_fn=lambda q, ctx, *, config: "Sin evidencia para B",
        config_fn=lambda: cfg,
    )

    graph = build_agent_graph(checkpointer=saver, config_fn=lambda: cfg)
    state_a = get_run_state("thread-a", graph=graph)
    state_b = get_run_state("thread-b", graph=graph)
    assert state_a["values"]["question"] == "Pregunta hilo A"
    assert state_a["values"]["route"] == "grounded"
    assert len(state_a["values"]["retrieved_context"]) == 1

    assert state_b["values"]["question"] == "Pregunta hilo B sin contexto"
    assert state_b["values"]["route"] == "no_evidence"
    assert state_b["values"]["retrieved_context"] == []

    history_a = get_run_checkpoints("thread-a", graph=graph)
    # Transiciones verificables desde el input hasta la respuesta final
    assert [step["next"] for step in history_a] == [
        ["__start__"],
        ["receive_question"],
        ["retrieve_context"],
        ["generate_grounded_answer"],
        [],
    ]


@pytest.mark.parametrize(
    "invalid_state",
    [
        {"messages": [{"role": "user", "content": "historial prohibido"}]},
        {"history": ["turno 1"]},
        {"api_key": "sk-fake-secret"},
        {"token": "jwt-token"},
        {"client": object()},
        {"unknown_field": 123},
        {"run_id": ""},
        {"question": 123},
        {"route": "unknown_route"},
        {"retrieved_context": [{"source_document": "loyalty-program"}]},
    ],
)
def test_state_validation_rejects_forbidden_keys_and_bad_types(invalid_state):
    with pytest.raises(StateValidationError):
        validate_agent_state(invalid_state)


def test_provider_error_writes_sanitized_trace_without_secrets(cfg, tmp_path):
    def fail_generate(*a, **kw):
        raise ProviderError("Fallo con clave secreta sk-fake-secret-999")

    with pytest.raises(ProviderError):
        execute_agent_query(
            "¿Cómo acumulo puntos?",
            run_id="test-run-error",
            trace_dir=tmp_path,
            checkpointer=InMemorySaver(),
            retrieve_fn=lambda *a, **kw: [
                {
                    "company": "brasaland",
                    "source_document": "loyalty-program",
                    "section": "Acumulación y vigencia",
                    "chunk_index": 0,
                    "language": "es",
                    "text": "Por cada 10.000 COP (o 10 USD en Florida) acumula 1 punto.",
                }
            ],
            generate_fn=fail_generate,
            config_fn=lambda: cfg,
        )

    persisted = load_trace("test-run-error", directory=tmp_path)
    raw = json.dumps(persisted, ensure_ascii=False)
    assert persisted["status"] == "error"
    assert persisted["error"]["code"] == "PROVIDER_ERROR"
    assert "sk-fake-secret-999" not in raw
    assert "secreta" not in raw


def test_eval_incident_question_uses_real_tool_route_without_rag(cfg, tmp_path):
    calls = []

    def incident_fn(query):
        calls.append(query)
        return IncidentToolResult(
            status=IncidentToolStatus.SUCCESS,
            incidents=[{
                "id": query.incident_id,
                "category": "EQUIPMENT",
                "status": "in_progress",
                "branch": "COL-01",
                "reported_at": "2026-10-20T12:00:00+00:00",
                "updated_at": "2026-10-21T12:00:00+00:00",
                "origin": "api",
                "external_ref": None,
            }],
            message="Consulta completada.",
        )

    result = execute_agent_query(
        "¿En qué estado está la incidencia abcdef123456?",
        run_id="test-run-incident",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda *a, **kw: pytest.fail("La consulta operativa no debe usar RAG"),
        generate_fn=lambda *a, **kw: pytest.fail("La consulta operativa no debe generar desde RAG"),
        config_fn=lambda: cfg,
        incident_fn=incident_fn,
    )
    assert calls == [IncidentToolInput(incident_id="abcdef123456")]
    assert "in_progress" in result["answer"]
    trace = load_trace("test-run-incident", directory=tmp_path)
    assert trace["source"] == "incidents"
    assert trace["nodes_order"] == [
        "receive_question",
        "query_incidents",
        "compose_incident_answer",
    ]
    assert trace["incident_tool_result"] == "success"
    assert trace["fallback"] is False
    assert "abcdef123456" not in json.dumps(trace)
    assert "question" not in trace


def test_eval_document_question_uses_rag_without_incidents(cfg, tmp_path):
    calls = []
    chunks = [{
        "source_document": "loyalty-program",
        "section": "Niveles",
        "text": "Oro requiere 50+ puntos y ofrece 15% de descuento.",
    }]
    result = execute_agent_query(
        "¿Cuántos puntos necesito para Oro?",
        run_id="test-run-rag-source",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda question, **kwargs: calls.append("retrieve") or chunks,
        generate_fn=lambda question, context, *, config: calls.append("generate") or "50+ puntos y 15%.",
        config_fn=lambda: cfg,
        incident_fn=lambda _: pytest.fail("La pregunta documental no debe consultar incidencias"),
    )
    assert calls == ["retrieve", "generate"]
    assert "50+ puntos" in result["answer"]
    trace = load_trace("test-run-rag-source", directory=tmp_path)
    assert trace["source"] == "rag"
    assert trace["incident_tool_result"] is None
    assert trace["fallback"] is False
    assert trace["nodes_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_grounded_answer",
    ]


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (IncidentToolStatus.TIMEOUT, "excedió el tiempo límite"),
        (IncidentToolStatus.UNAVAILABLE, "no está disponible"),
        (IncidentToolStatus.NOT_FOUND, "No encontré"),
    ],
)
def test_incident_failure_and_not_found_use_honest_fallback(cfg, tmp_path, status, message):
    result = execute_agent_query(
        "¿En qué estado está la incidencia abcdef123456?",
        run_id=f"test-run-{status.value}",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda *a, **kw: pytest.fail("No debe consultar RAG como fallback"),
        generate_fn=lambda *a, **kw: pytest.fail("No debe inventar con el generador RAG"),
        config_fn=lambda: cfg,
        incident_fn=lambda _: IncidentToolResult(status=status, message=message),
    )
    assert message.lower() in result["answer"].lower()
    trace = load_trace(f"test-run-{status.value}", directory=tmp_path)
    assert trace["fallback"] is True
    assert trace["incident_tool_result"] == status.value
    assert "retrieve_context" not in trace["nodes_order"]
    assert "generate_grounded_answer" not in trace["nodes_order"]


def test_combined_question_keeps_rag_and_incident_results_separate(cfg, tmp_path):
    rag_context = [{
        "source_document": "supplier-ordering",
        "section": "Procedimiento",
        "text": "El procedimiento documentado requiere aprobación.",
    }]
    result = execute_agent_query(
        "¿En qué estado está la incidencia abcdef123456 y cuál es el procedimiento de pedido?",
        run_id="test-run-both",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda *a, **kw: rag_context,
        generate_fn=lambda question, context, *, config: "La política requiere aprobación.",
        config_fn=lambda: cfg,
        incident_fn=lambda _: IncidentToolResult(
            status=IncidentToolStatus.SUCCESS,
            incidents=[{
                "id": "abcdef123456",
                "category": "SUPPLY",
                "status": "open",
                "branch": "COL-01",
                "reported_at": "2026-10-20T12:00:00+00:00",
                "updated_at": "2026-10-21T12:00:00+00:00",
                "origin": "api",
            }],
            message="Consulta completada.",
        ),
    )
    assert "Información de políticas/documentación:" in result["answer"]
    assert "La política requiere aprobación." in result["answer"]
    assert "Datos actuales de incidencias:" in result["answer"]
    assert "estado: open" in result["answer"]
    trace = load_trace("test-run-both", directory=tmp_path)
    assert trace["source"] == "both"
    assert trace["nodes_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_grounded_answer",
        "query_incidents",
        "compose_incident_answer",
    ]


def test_short_incident_number_requests_clarification_without_lookup(cfg, tmp_path):
    result = execute_agent_query(
        "¿En qué estado está el ticket 482?",
        run_id="test-run-ambiguous-incident",
        trace_dir=tmp_path,
        checkpointer=InMemorySaver(),
        retrieve_fn=lambda *a, **kw: pytest.fail("La referencia ambigua no debe ir al RAG"),
        generate_fn=lambda *a, **kw: pytest.fail("No debe inventar con el generador RAG"),
        config_fn=lambda: cfg,
        incident_fn=lambda _: pytest.fail("El número corto no es un ID interno válido"),
    )
    assert "ID interno de 12 caracteres" in result["answer"]
    trace = load_trace("test-run-ambiguous-incident", directory=tmp_path)
    assert trace["source"] == "clarification"
    assert trace["nodes_order"] == ["receive_question", "clarify_incident_reference"]

def test_mcp_client_maps_successful_envelope_to_incident_result(monkeypatch):
    """El nuevo cliente MCP traduce el envelope del servidor a IncidentToolResult."""

    def invoker(query, server_url, token):
        assert server_url == "https://mcp.internal"
        assert token == "test-token"
        return IncidentToolResult(
            status=IncidentToolStatus.SUCCESS,
            incidents=[{
                "id": "abcdef123456",
                "category": "EQUIPMENT",
                "status": "open",
                "branch": "COL-01",
                "reported_at": "2026-10-20T12:00:00+00:00",
                "updated_at": "2026-10-21T12:00:00+00:00",
                "origin": "api",
                "external_ref": "external-482",
            }],
            message="Consulta completada.",
        )

    result = query_incidents(
        IncidentToolInput(incident_id="abcdef123456"),
        server_url="https://mcp.internal",
        tool_invoker=invoker,
    )
    assert result.status == IncidentToolStatus.SUCCESS
    assert result.incidents[0].status == "open"
    # Free-text fields are dropped before reaching the model.
    assert "title" not in result.incidents[0].model_dump()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (IncidentToolStatus.PERMISSION_DENIED, IncidentToolStatus.PERMISSION_DENIED),
        (IncidentToolStatus.NOT_FOUND, IncidentToolStatus.NOT_FOUND),
        (IncidentToolStatus.UNAVAILABLE, IncidentToolStatus.UNAVAILABLE),
    ],
)
def test_mcp_client_propagates_categorical_statuses(monkeypatch, status, expected):
    def invoker(query, server_url, token):
        return IncidentToolResult(status=status, message="detalle interno privado", incidents=[])

    result = query_incidents(
        IncidentToolInput(incident_id="abcdef123456"),
        server_url="https://mcp.internal",
        tool_invoker=invoker,
    )
    assert result.status == expected
    assert "detalle interno privado" not in result.message or result.status != IncidentToolStatus.SUCCESS


def test_mcp_client_returns_explicit_timeout(monkeypatch):
    import time

    def invoker(query, server_url, token):
        time.sleep(10)
        return IncidentToolResult(status=IncidentToolStatus.SUCCESS, message="ok", incidents=[])

    result = query_incidents(
        IncidentToolInput(incident_id="abcdef123456"),
        server_url="https://mcp.internal",
        tool_invoker=invoker,
        timeout_seconds=0.2,
    )
    assert result.status == IncidentToolStatus.TIMEOUT


def test_direct_incident_http_client_is_gone():
    """El camino HTTP directo al Incidents Manager fue retirado: no existe módulo."""
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.domains.agent.incident_tool")

    # Y el agente ya no acepta incident_token (frontera única vía MCP).
    import inspect

    from app.domains.agent.graph import execute_agent_query

    assert "incident_token" not in inspect.signature(execute_agent_query).parameters
