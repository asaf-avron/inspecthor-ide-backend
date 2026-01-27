"""Add projects and unit_links tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('project_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('api_key_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for projects
    op.create_index('ix_projects_api_key_hash', 'projects', ['api_key_hash'])
    op.create_index('ix_projects_updated_at', 'projects', ['updated_at'], postgresql_ops={'updated_at': 'DESC'})
    op.create_index(
        'ix_projects_api_key_hash_name_lower',
        'projects',
        ['api_key_hash', sa.text('LOWER(name)')],
        unique=True
    )
    
    # Drop old files table if it exists (SQLite version)
    op.execute('DROP TABLE IF EXISTS files')
    
    # Create new files table with UUID and foreign key
    op.create_table(
        'files',
        sa.Column('file_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Enum('md', 'dfy', 'unit', name='file_type_enum'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
    )
    
    # Create indexes and unique constraint for files
    op.create_index('ix_files_project_id', 'files', ['project_id'])
    op.create_index('ix_files_project_id_filename', 'files', ['project_id', 'filename'], unique=True)
    
    # Create unit_links table
    op.create_table(
        'unit_links',
        sa.Column('link_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('root_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unit_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dafny_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('verification_status', sa.Enum('unknown', 'verified', 'failed', 'pending', name='verification_status_enum'), nullable=False, server_default='unknown'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['root_file_id'], ['files.file_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_file_id'], ['files.file_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dafny_file_id'], ['files.file_id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('unit_links')
    op.drop_table('files')
    op.drop_table('projects')
    op.execute('DROP TYPE IF EXISTS file_type_enum')
    op.execute('DROP TYPE IF EXISTS verification_status_enum')
