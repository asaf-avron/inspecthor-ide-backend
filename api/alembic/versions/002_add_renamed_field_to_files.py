"""Add renamed field to files table

Revision ID: 002_add_renamed
Revises: 001_initial
Create Date: 2026-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_renamed'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add renamed column to files table with default False
    op.add_column('files', sa.Column('renamed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove renamed column
    op.drop_column('files', 'renamed')
