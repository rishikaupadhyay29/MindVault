"""Add document attachments to notes.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "note_attachments",
        sa.Column(
            "note_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "note_id <> document_id",
            name="ck_note_attachments_not_self",
        ),
    )

    op.create_index(
        "ix_note_attachments_document_id",
        "note_attachments",
        ["document_id"],
    )


def downgrade():
    op.drop_index(
        "ix_note_attachments_document_id",
        table_name="note_attachments",
    )
    op.drop_table("note_attachments")