"""chunks table (pgvector), HNSW index, row-level security policies

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Fixed at migration-authoring time to match the default embedding provider
# (Voyage voyage-3-large, 1024 dims). Changing embedding provider/model dimension
# is an operational migration (new column + full re-embed), not a hot-swap.
EMBEDDING_DIMENSIONS = 1024

RLS_TABLES = ["documents", "chunks", "ingestion_jobs", "eval_runs"]

# tenants/api_keys are intentionally excluded from RLS_TABLES -- see app/db/models/api_key.py
# for why (looked up by hash before a tenant is known). They still need grants below.
ALL_APP_TABLES = ["tenants", "api_keys", *RLS_TABLES]


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Row-level security: defense-in-depth alongside application-level tenant_id
    # filtering. Fails closed -- current_setting() in strict mode raises if
    # app.tenant_id was never set on the session, rather than returning all rows.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id')::uuid)"
        )

    # The API/worker connect as the restricted `rag_app` role (created in
    # docker/postgres/init.sh), never as the migrator/bootstrap superuser -- RLS is
    # always bypassed for superusers, so a non-superuser role is what makes the
    # policies above actually take effect.
    for table in ALL_APP_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rag_app")


def downgrade() -> None:
    for table in ALL_APP_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM rag_app")
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("chunks")
