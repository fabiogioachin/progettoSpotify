"""add compound index user_id played_at on recent_plays

Revision ID: c8d1a3f5e290
Revises: a3c7e1f09b24
Create Date: 2026-04-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d1a3f5e290"
down_revision: Union[str, Sequence[str], None] = "a3c7e1f09b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add compound index on (user_id, played_at) for recent_plays."""
    op.create_index(
        "ix_recent_plays_user_played",
        "recent_plays",
        ["user_id", "played_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove compound index."""
    op.drop_index("ix_recent_plays_user_played", table_name="recent_plays")
