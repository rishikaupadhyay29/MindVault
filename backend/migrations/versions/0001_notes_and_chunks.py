"""notes and note_chunks with pgvector

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

status = postgresql.ENUM("pending", "processing", "indexed", "failed", name="processing_status", create_type=False)


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False, server_default="Untitled"),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("indexed_hash", sa.String(64)),
        sa.Column("processing_status", status, nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notes_created_at", "notes", ["created_at"])
    op.create_index("ix_notes_processing_status", "notes", ["processing_status"])
    op.create_table(
        "note_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("note_id", "chunk_index", name="uq_note_chunks_note_idx"),
    )
    op.execute(
        "CREATE INDEX ix_note_chunks_embedding_hnsw ON note_chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade():
    op.drop_table("note_chunks")
    op.drop_table("notes")
    status.drop(op.get_bind(), checkfirst=True)
