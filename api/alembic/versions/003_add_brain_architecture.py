"""Add Brain Architecture support

Revision ID: 003_brain_architecture
Revises: 002_add_renamed
Create Date: 2026-02-04 12:00:00.000000

Adds support for the .inspecthor/ Brain architecture:
- Component UUID tracking for blueprints
- Registry path for components
- Sync status for AI-Gapped Development
- Spec and Dafny hashes for tamper detection
- Ledger entries table for verification history
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_brain_architecture'
down_revision: Union[str, None] = '002_add_renamed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Brain architecture fields and tables"""

    # Add fields to blueprints table
    op.add_column('blueprints',
        sa.Column('component_uuid', sa.String(64), nullable=True)
    )
    op.add_column('blueprints',
        sa.Column('registry_path', sa.String(512), nullable=True)
    )
    op.add_column('blueprints',
        sa.Column('sync_status',
            sa.Enum('clean', 'dirty', 'verifying', 'error', name='sync_status_enum'),
            nullable=False,
            server_default='clean'
        )
    )
    op.add_column('blueprints',
        sa.Column('spec_hash', sa.String(71), nullable=True)
    )
    op.add_column('blueprints',
        sa.Column('dafny_hash', sa.String(71), nullable=True)
    )
    op.add_column('blueprints',
        sa.Column('last_harmonized', sa.DateTime, nullable=True)
    )

    # Create indexes
    op.create_index('ix_blueprints_component_uuid', 'blueprints', ['component_uuid'], unique=True)

    # Create ledger_entries table
    op.create_table(
        'ledger_entries',
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('component_uuid', sa.String(64), nullable=False, index=True),
        sa.Column('blueprint_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('code_hash', sa.String(71), nullable=False),
        sa.Column('status',
            sa.Enum('verified', 'failed', 'pending', 'timeout', 'error', name='ledger_status_enum'),
            nullable=False
        ),
        sa.Column('proof_obligations', sa.Text, nullable=True),
        sa.Column('dafny_output', sa.Text, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('dafny_version', sa.String(50), nullable=True),
        sa.Column('verification_time_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['blueprint_id'], ['blueprints.blueprint_id'], ondelete='CASCADE')
    )

    # Create indexes for ledger_entries
    op.create_index('ix_ledger_component_uuid', 'ledger_entries', ['component_uuid'])
    op.create_index('ix_ledger_blueprint_id', 'ledger_entries', ['blueprint_id'])
    op.create_index('ix_ledger_status', 'ledger_entries', ['status'])
    op.create_index('ix_ledger_created_at', 'ledger_entries', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('ix_ledger_component_created', 'ledger_entries', ['component_uuid', 'created_at'], postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    """Remove Brain architecture fields and tables"""

    # Drop ledger_entries table and indexes
    op.drop_index('ix_ledger_component_created', table_name='ledger_entries')
    op.drop_index('ix_ledger_created_at', table_name='ledger_entries')
    op.drop_index('ix_ledger_status', table_name='ledger_entries')
    op.drop_index('ix_ledger_blueprint_id', table_name='ledger_entries')
    op.drop_index('ix_ledger_component_uuid', table_name='ledger_entries')
    op.drop_table('ledger_entries')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS ledger_status_enum')

    # Drop blueprint fields
    op.drop_index('ix_blueprints_component_uuid', table_name='blueprints')
    op.drop_column('blueprints', 'last_harmonized')
    op.drop_column('blueprints', 'dafny_hash')
    op.drop_column('blueprints', 'spec_hash')
    op.drop_column('blueprints', 'sync_status')
    op.drop_column('blueprints', 'registry_path')
    op.drop_column('blueprints', 'component_uuid')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS sync_status_enum')
