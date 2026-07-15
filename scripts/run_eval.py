"""Runs the golden Q&A eval harness and prints a summary.

Each golden example is ingested into its own scratch tenant by the harness (never
into the caller's tenant), so this script needs its own throwaway tenant only to
own the persisted EvalRun record.

Usage: docker compose run --rm api python scripts/run_eval.py [path/to/dataset.yaml]
"""

import asyncio
import sys
import uuid
from pathlib import Path

from app.config import get_settings
from app.db.base import get_session_factory
from app.db.models.eval_run import EvalRun
from app.db.models.tenant import Tenant
from app.db.session import tenant_session
from app.observability.evals.golden_dataset import load_golden_dataset
from app.observability.evals.harness import EvalHarness
from app.providers.registry import get_embedding_provider, get_llm_provider

DEFAULT_DATASET = (
    Path(__file__).resolve().parent.parent / "tests" / "evals" / "golden_qa.sample.yaml"
)


async def main() -> None:
    settings = get_settings()
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    dataset = load_golden_dataset(dataset_path)

    harness = EvalHarness(settings, get_embedding_provider(), get_llm_provider())
    summary = await harness.run(dataset, dataset_name=dataset_path.stem)

    bookkeeping_tenant_id = uuid.uuid4()
    async with get_session_factory()() as db:
        db.add(Tenant(id=bookkeeping_tenant_id, name=f"eval-cli:{bookkeeping_tenant_id}"))
        await db.commit()

    async with tenant_session(bookkeeping_tenant_id) as session:
        session.add(
            EvalRun(
                tenant_id=bookkeeping_tenant_id,
                dataset_name=dataset_path.stem,
                results=summary,
            )
        )

    print(f"Dataset: {dataset_path.name} ({len(dataset)} examples)")
    print(f"Failed: {summary['failed_count']}")
    print(f"Recall@{settings.retrieval_top_k}: {summary['recall_at_k']:.2f}")
    print(f"Avg groundedness: {summary['avg_groundedness']:.2f}/5")
    print(f"Avg relevance: {summary['avg_relevance']:.2f}/5")


if __name__ == "__main__":
    asyncio.run(main())
