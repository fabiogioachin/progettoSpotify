"""add artist_genres table, drop listening_snapshots

Revision ID: a3c7e1f09b24
Revises: b9ad90a8dada
Create Date: 2026-03-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7e1f09b24'
down_revision: Union[str, Sequence[str], None] = 'b9ad90a8dada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create artist_genres cache table
    op.create_table('artist_genres',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('artist_spotify_id', sa.String(length=64), nullable=False),
        sa.Column('artist_name', sa.String(length=500), nullable=True),
        sa.Column('genres', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('cached_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_artist_genres_artist_spotify_id'),
        'artist_genres',
        ['artist_spotify_id'],
        unique=True,
    )

    # Drop dead table — never written to
    op.drop_table('listening_snapshots')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate listening_snapshots
    op.create_table('listening_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('avg_energy', sa.Float(), nullable=True),
        sa.Column('avg_valence', sa.Float(), nullable=True),
        sa.Column('avg_danceability', sa.Float(), nullable=True),
        sa.Column('avg_acousticness', sa.Float(), nullable=True),
        sa.Column('avg_instrumentalness', sa.Float(), nullable=True),
        sa.Column('avg_speechiness', sa.Float(), nullable=True),
        sa.Column('avg_liveness', sa.Float(), nullable=True),
        sa.Column('avg_tempo', sa.Float(), nullable=True),
        sa.Column('top_genre', sa.String(length=255), nullable=True),
        sa.Column('genre_distribution', sa.Text(), nullable=True),
        sa.Column('track_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_listening_snapshots_user_id', 'listening_snapshots', ['user_id'])

    # Drop artist_genres
    op.drop_index(
        op.f('ix_artist_genres_artist_spotify_id'),
        table_name='artist_genres',
    )
    op.drop_table('artist_genres')
