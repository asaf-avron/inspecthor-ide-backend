"""Add parent_path to files

Revision ID: 004_add_parent_path
Revises: 003_brain_architecture
Create Date: 2026-10-28 23:00:00.000000

The refinement and runtime-verification routes group files by component directory
(for example `components/auth`). Files in the blueprint root have no parent path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_add_parent_path'
down_revision: Union[str, None] = '003_brain_architecture'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('files', sa.Column('parent_path', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('files', 'parent_path')
