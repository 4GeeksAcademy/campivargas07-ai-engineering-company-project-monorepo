from pydantic import BaseModel, Field, field_validator


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La pregunta no puede estar vacía.")
        return value.strip()


class KnowledgeQueryResponse(BaseModel):
    answer: str = Field(min_length=1)
