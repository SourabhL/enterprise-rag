import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.query import CitationResponse, QueryRequest, QueryResponse, UsageResponse
from app.config import get_settings
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_tenant_id_dep, get_tenant_db
from app.generation.service import build_rag_service
from app.observability.metrics import record_llm_usage
from app.retrieval.prompt import extract_citations

router = APIRouter(prefix="/query", tags=["query"], dependencies=[Depends(rate_limit_dependency)])


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    tenant_id=Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> QueryResponse:
    service = build_rag_service(db, get_settings())
    result = await service.answer(tenant_id, body.query)
    return QueryResponse(
        answer=result.answer,
        citations=[
            CitationResponse(document_id=c.document_id, chunk_id=c.chunk_id, snippet=c.snippet)
            for c in result.citations
        ],
        usage=UsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cache_read_input_tokens=result.usage.cache_read_input_tokens,
            cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
        ),
    )


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    tenant_id=Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> StreamingResponse:
    service = build_rag_service(db, get_settings())

    async def event_generator():
        chunks, stream = await service.answer_stream(tenant_id, body.query)
        parts: list[str] = []
        usage = None
        async for event in stream:
            if event.is_final:
                usage = event.usage
            else:
                parts.append(event.delta)
                yield f"event: delta\ndata: {json.dumps({'text': event.delta})}\n\n"

        answer = "".join(parts)
        citations = extract_citations(answer, chunks)
        if usage is not None:
            record_llm_usage(tenant_id, usage)
        payload = {
            "citations": [
                {"document_id": c.document_id, "chunk_id": c.chunk_id, "snippet": c.snippet}
                for c in citations
            ],
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_input_tokens": usage.cache_read_input_tokens,
                "cache_creation_input_tokens": usage.cache_creation_input_tokens,
            }
            if usage
            else None,
        }
        yield f"event: done\ndata: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
