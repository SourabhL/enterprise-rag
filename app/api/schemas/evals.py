import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GoldenExampleRequest(BaseModel):
    question: str
    document_text: str
    document_filename: str = "eval-doc.txt"
    expected_facts: list[str] = Field(default_factory=list)


class RunEvalRequest(BaseModel):
    dataset_name: str
    examples: list[GoldenExampleRequest] = Field(min_length=1)


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_name: str
    results: dict
    created_at: datetime
