"""add pgvector embedding

Revision ID: a1b2c3d4e5f6
Revises: db61259f27d7
Create Date: 2026-06-24 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'db61259f27d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.add_column('user_memories', sa.Column('embedding', Vector(3072), nullable=True))


def downgrade() -> None:
    op.drop_column('user_memories', 'embedding')
    op.execute('DROP EXTENSION IF EXISTS vector')
