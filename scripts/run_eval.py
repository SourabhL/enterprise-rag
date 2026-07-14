"""Runs the golden Q&A eval harness against a scratch tenant and prints a summary.

Usage: docker compose run --rm api python scripts/run_eval.py [path/to/dataset.yaml]
"""

import asyncio
import sys
import uuid
from pathlib import Path

from app.config import get_settings
from app.db.models.tenant import Tenant
from app.db.session import get_raw_db
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

    tenant_id = uuid.uuid4()
    async for db in get_raw_db():
        db.add(Tenant(id=tenant_id, name=f"eval-scratch-{tenant_id}"))
        await db.commit()
        break

    harness = EvalHarness(settings, get_embedding_provider(), get_llm_provider())
    _, summary = await harness.run(dataset, tenant_id, dataset_name=dataset_path.stem)

    print(f"Dataset: {dataset_path.name} ({len(dataset)} examples)")
    print(f"Recall@{settings.retrieval_top_k}: {summary['recall_at_k']:.2f}")
    print(f"Avg groundedness: {summary['avg_groundedness']:.2f}/5")
    print(f"Avg relevance: {summary['avg_relevance']:.2f}/5")


if __name__ == "__main__":
    asyncio.run(main())
