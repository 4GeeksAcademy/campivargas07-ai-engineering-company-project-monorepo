"""LangGraph support agent evaluations and structural/checkpoint tests (Part 1)."""
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
import pytest

from app.domains.agent.graph import (
    COMPILED_AGENT_GRAPH,
    InvalidQuestionError,
    execute_agent_query,
    get_run_checkpoints,
    get_run_state,
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
