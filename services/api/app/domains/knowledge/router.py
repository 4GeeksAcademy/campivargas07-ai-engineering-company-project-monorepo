from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.domains.auth.dependencies import get_current_user
from app.domains.knowledge.schemas import KnowledgeQueryRequest, KnowledgeQueryResponse
from data.pipelines.query import query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/query", response_model=KnowledgeQueryResponse)
def query_knowledge(
    request: KnowledgeQueryRequest,
    current_user: dict = Depends(get_current_user),
) -> KnowledgeQueryResponse:
    """Answer from the official knowledge base; requires an active session."""
    del current_user  # Authentication is the authorization boundary for this internal tool.
    try:
        answer = query(request.question)
    except Exception as exc:
        logger.exception("Knowledge query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La base de conocimiento no está disponible temporalmente.",
        ) from exc
    return KnowledgeQueryResponse(answer=answer)
