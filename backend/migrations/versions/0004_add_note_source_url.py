"""Add source URL to notes for bookmarks.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notes",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )


def downgrade():
    op.drop_column("notes", "source_url")
