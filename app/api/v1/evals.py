import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.evals import EvalRunResponse, RunEvalRequest
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.security import get_current_tenant_id_dep, get_tenant_db
from app.db.models.eval_run import EvalRun
from app.observability.evals.golden_dataset import GoldenExample
from app.observability.evals.harness import EvalHarness
from app.providers.registry import get_embedding_provider, get_llm_provider

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse, status_code=201)
async def run_eval(
    body: RunEvalRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> EvalRun:
    dataset = [
        GoldenExample(
            question=e.question,
            document_text=e.document_text,
            document_filename=e.document_filename,
            expected_facts=e.expected_facts,
        )
        for e in body.examples
    ]
    # EvalHarness ingests each example's document into its own scratch tenant --
    # never the caller's tenant -- so eval fixture content can never leak into the
    # caller's live retrieval corpus. Only the resulting summary (no document
    # content) is persisted here, under the caller's own tenant.
    harness = EvalHarness(get_settings(), get_embedding_provider(), get_llm_provider())
    summary = await harness.run(dataset, dataset_name=body.dataset_name)

    eval_run = EvalRun(tenant_id=tenant_id, dataset_name=body.dataset_name, results=summary)
    db.add(eval_run)
    await db.flush()
    await db.refresh(eval_run)
    return eval_run


@router.get("/{eval_run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    eval_run_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> EvalRun:
    eval_run = await db.get(EvalRun, eval_run_id)
    if eval_run is None or eval_run.tenant_id != tenant_id:
        raise NotFoundError(f"Eval run {eval_run_id} not found")
    return eval_run
