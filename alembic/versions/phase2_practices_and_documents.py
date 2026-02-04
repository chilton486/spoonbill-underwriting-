"""Phase 2: Add practices, claim_documents, update users and claims for multi-tenant

Revision ID: phase2_practices
Revises: 3c116f50c1d4
Create Date: 2026-02-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'phase2_practices'
down_revision: Union[str, None] = '3c116f50c1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('practices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_practices_id'), 'practices', ['id'], unique=False)

    conn = op.get_bind()
    conn.execute(sa.text("INSERT INTO practices (id, name, status) VALUES (1, 'Demo Practice', 'ACTIVE')"))

    op.add_column('users', sa.Column('practice_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_users_practice_id'), 'users', ['practice_id'], unique=False)
    op.create_foreign_key('fk_users_practice_id', 'users', 'practices', ['practice_id'], ['id'])

    conn.execute(sa.text("UPDATE users SET role = 'SPOONBILL_ADMIN' WHERE role = 'ADMIN'"))
    conn.execute(sa.text("UPDATE users SET role = 'SPOONBILL_OPS' WHERE role = 'OPS'"))

    op.add_column('claims', sa.Column('practice_id_new', sa.Integer(), nullable=True))
    
    conn.execute(sa.text("UPDATE claims SET practice_id_new = 1"))
    
    op.drop_index('ix_claims_practice_id', table_name='claims')
    op.drop_column('claims', 'practice_id')
    
    op.alter_column('claims', 'practice_id_new', new_column_name='practice_id', nullable=False)
    op.create_index(op.f('ix_claims_practice_id'), 'claims', ['practice_id'], unique=False)
    op.create_foreign_key('fk_claims_practice_id', 'claims', 'practices', ['practice_id'], ['id'])

    op.create_table('claim_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], name='fk_claim_documents_claim_id'),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], name='fk_claim_documents_practice_id'),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name='fk_claim_documents_uploaded_by'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claim_documents_id'), 'claim_documents', ['id'], unique=False)
    op.create_index(op.f('ix_claim_documents_claim_id'), 'claim_documents', ['claim_id'], unique=False)
    op.create_index(op.f('ix_claim_documents_practice_id'), 'claim_documents', ['practice_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_claim_documents_practice_id'), table_name='claim_documents')
    op.drop_index(op.f('ix_claim_documents_claim_id'), table_name='claim_documents')
    op.drop_index(op.f('ix_claim_documents_id'), table_name='claim_documents')
    op.drop_table('claim_documents')

    op.drop_constraint('fk_claims_practice_id', 'claims', type_='foreignkey')
    op.drop_index(op.f('ix_claims_practice_id'), table_name='claims')
    
    op.add_column('claims', sa.Column('practice_id_old', sa.String(length=255), nullable=True))
    
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE claims SET practice_id_old = CAST(practice_id AS VARCHAR)"))
    
    op.drop_column('claims', 'practice_id')
    op.alter_column('claims', 'practice_id_old', new_column_name='practice_id', nullable=True)
    op.create_index('ix_claims_practice_id', 'claims', ['practice_id'], unique=False)

    conn.execute(sa.text("UPDATE users SET role = 'ADMIN' WHERE role = 'SPOONBILL_ADMIN'"))
    conn.execute(sa.text("UPDATE users SET role = 'OPS' WHERE role = 'SPOONBILL_OPS'"))

    op.drop_constraint('fk_users_practice_id', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_practice_id'), table_name='users')
    op.drop_column('users', 'practice_id')

    op.drop_index(op.f('ix_practices_id'), table_name='practices')
    op.drop_table('practices')
