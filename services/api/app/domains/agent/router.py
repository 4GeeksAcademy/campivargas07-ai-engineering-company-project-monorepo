"""Authenticated FastAPI endpoint for the LangGraph support agent (Part 1 + MEM-092 memory)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.domains.agent.graph import InvalidQuestionError, execute_agent_query
from app.domains.agent.memory import MemoryPolicy
from app.domains.auth.dependencies import get_current_user
from data.process.config import ConfigurationError, ProviderError, RagError

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(get_current_user)],
)


class AgentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)
    client_request_id: str | None = Field(default=None, max_length=128)


class AgentQueryResponse(BaseModel):
    answer: str
    conversation_id: str | None = None
    run_id: str | None = None
    route: str | None = None
    memory_proposal: dict | None = None


@router.post("/query", response_model=AgentQueryResponse, response_model_exclude_none=True)
def query_agent(
    body: AgentQueryRequest,
    current_user: dict = Depends(get_current_user),
) -> AgentQueryResponse:
    try:
        result = execute_agent_query(
            body.question,
            thread_id=body.conversation_id,
            conversation_id=body.conversation_id,
            user_uuid=current_user.get("uuid"),
            memory_policy=MemoryPolicy.from_env(),
        )
        return AgentQueryResponse(
            answer=result["answer"],
            conversation_id=result.get("conversation_id"),
            run_id=result.get("run_id"),
            route=result.get("route"),
            memory_proposal=result.get("memory_proposal"),
        )
    except InvalidQuestionError:
        raise HTTPException(422, "La pregunta no puede estar vacía.") from None
    except ConfigurationError:
        raise HTTPException(503, "La base de conocimiento aún no está configurada.") from None
    except ProviderError:
        raise HTTPException(502, "No se pudo generar la respuesta. Inténtalo de nuevo.") from None
    except RagError:
        raise HTTPException(503, "La base de conocimiento no está disponible. Inténtalo de nuevo.") from None
    except Exception:
        raise HTTPException(500, "Error interno al procesar la consulta del agente.") from None
