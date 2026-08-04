"""add track_metadata table

Revision ID: e71b4c92f0aa
Revises: d58a13c8ad7a
Create Date: 2026-08-04 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e71b4c92f0aa'
down_revision: Union[str, Sequence[str], None] = 'd58a13c8ad7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('track_metadata',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('track_spotify_id', sa.String(length=255), nullable=False),
        sa.Column('album_name', sa.String(length=500), nullable=True),
        sa.Column('album_image', sa.String(), nullable=True),
        sa.Column('preview_url', sa.String(), nullable=True),
        sa.Column('cached_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_track_metadata_track_spotify_id'),
        'track_metadata',
        ['track_spotify_id'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_track_metadata_track_spotify_id'), table_name='track_metadata')
    op.drop_table('track_metadata')
