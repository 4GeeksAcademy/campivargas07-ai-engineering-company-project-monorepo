"""Authenticated FastAPI endpoint for the LangGraph support agent (Part 1)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.domains.agent.graph import InvalidQuestionError, execute_agent_query
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


class AgentQueryResponse(BaseModel):
    answer: str


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    body: AgentQueryRequest,
) -> AgentQueryResponse:
    try:
        result = execute_agent_query(body.question)
        return AgentQueryResponse(answer=result["answer"])
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
