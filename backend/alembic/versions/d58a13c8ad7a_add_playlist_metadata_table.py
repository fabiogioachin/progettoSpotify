"""add playlist_metadata table

Revision ID: d58a13c8ad7a
Revises: c8d1a3f5e290
Create Date: 2026-04-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd58a13c8ad7a'
down_revision: Union[str, Sequence[str], None] = 'c8d1a3f5e290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('playlist_metadata',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('playlist_id', sa.String(length=64), nullable=False),
        sa.Column('track_count', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('is_owner', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'playlist_id', name='uq_playlist_metadata_user_pid'),
    )
    op.create_index(op.f('ix_playlist_metadata_user_id'), 'playlist_metadata', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_playlist_metadata_user_id'), table_name='playlist_metadata')
    op.drop_table('playlist_metadata')
