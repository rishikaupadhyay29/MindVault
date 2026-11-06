"""users, note ownership/tags/source, conversations, messages

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
NOW = sa.func.now()


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.add_column("notes", sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")))
    op.add_column("notes", sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("notes", sa.Column("source_type", sa.String(20), nullable=False, server_default="note"))
    op.add_column("notes", sa.Column("source_filename", sa.String(255)))
    op.create_index("ix_notes_owner_id", "notes", ["owner_id"])
    op.execute("CREATE INDEX ix_notes_tags ON notes USING gin (tags)")
    op.create_table(
        "conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False, server_default="New conversation"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("conversation_id", UUID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("grounded", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade():
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_notes_tags", "notes")
    op.drop_index("ix_notes_owner_id", "notes")
    for c in ("source_filename", "source_type", "tags", "owner_id"):
        op.drop_column("notes", c)
    op.drop_table("users")
