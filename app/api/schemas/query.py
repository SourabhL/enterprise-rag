import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)


class CitationResponse(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    snippet: str


class UsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    usage: UsageResponse
