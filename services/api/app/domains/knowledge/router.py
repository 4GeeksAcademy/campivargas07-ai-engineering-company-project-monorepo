from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.domains.auth.dependencies import get_current_user
from data.pipelines.rag import query
from data.process.config import ConfigurationError, ProviderError, RagError

router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)


class Answer(BaseModel):
    answer: str


@router.post("/query", response_model=Answer)
def ask(body: Question) -> Answer:
    try:
        return Answer(answer=query(body.question))
    except ConfigurationError:
        raise HTTPException(503, "La base de conocimiento aún no está configurada.") from None
    except ProviderError:
        raise HTTPException(502, "No se pudo generar la respuesta. Inténtalo de nuevo.") from None
    except RagError:
        raise HTTPException(503, "La base de conocimiento no está disponible. Inténtalo de nuevo.") from None
