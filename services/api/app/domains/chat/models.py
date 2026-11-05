from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    location_id: str = Field(min_length=1, max_length=32)


class ChatSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    agent_id: str = "manager_support"
    user_id: str
    location_id: str
    status: Literal["active", "interrupted", "closed"] = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str
    session_id: str
    generation_id: str | None = None
    role: Literal["user", "assistant"]
    content: str = ""
    status: Literal["complete", "interrupted", "streaming"] = "complete"
    is_complete: bool = True
    sequence: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None


class ChatEventEnvelope(BaseModel):
    event: str
    data: dict[str, Any]