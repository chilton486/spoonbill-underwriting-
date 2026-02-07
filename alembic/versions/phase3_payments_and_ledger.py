"""Phase 3: Add payment_intents, ledger_accounts, ledger_entries, and claim payment fields

Revision ID: phase3_payments
Revises: phase2_practices
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'phase3_payments'
down_revision: Union[str, None] = 'phase2_practices'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('claims', sa.Column('payment_exception', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('claims', sa.Column('exception_code', sa.Text(), nullable=True))

    op.create_table('ledger_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('practice_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], name='fk_ledger_accounts_practice_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_type', 'practice_id', 'currency', name='uq_ledger_account_type_practice_currency')
    )
    op.create_index('idx_ledger_accounts_type', 'ledger_accounts', ['account_type'], unique=False)
    op.create_index('idx_ledger_accounts_practice_id', 'ledger_accounts', ['practice_id'], unique=False)

    op.create_table('payment_intents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('practice_id', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='QUEUED'),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='SIMULATED'),
        sa.Column('provider_reference', sa.String(length=255), nullable=True),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('failure_message', sa.String(length=1000), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], name='fk_payment_intents_claim_id'),
        sa.ForeignKeyConstraint(['practice_id'], ['practices.id'], name='fk_payment_intents_practice_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id', name='uq_payment_intents_claim_id'),
        sa.UniqueConstraint('idempotency_key', name='uq_payment_intents_idempotency_key')
    )
    op.create_index('idx_payment_intents_claim_id', 'payment_intents', ['claim_id'], unique=True)
    op.create_index('idx_payment_intents_practice_id', 'payment_intents', ['practice_id'], unique=False)
    op.create_index('idx_payment_intents_status', 'payment_intents', ['status'], unique=False)

    op.create_table('ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('related_type', sa.String(length=50), nullable=False),
        sa.Column('related_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['ledger_accounts.id'], name='fk_ledger_entries_account_id'),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], name='fk_ledger_entries_claim_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount_cents > 0', name='ck_ledger_entry_amount_positive'),
        sa.UniqueConstraint('idempotency_key', name='uq_ledger_entries_idempotency_key')
    )
    op.create_index('idx_ledger_entries_account_id', 'ledger_entries', ['account_id'], unique=False)
    op.create_index('idx_ledger_entries_related', 'ledger_entries', ['related_type', 'related_id'], unique=False)
    op.create_index('idx_ledger_entries_claim_id', 'ledger_entries', ['claim_id'], unique=False)
    op.create_index('idx_ledger_entries_status', 'ledger_entries', ['status'], unique=False)

    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO ledger_accounts (id, account_type, currency, practice_id)
        VALUES 
            (gen_random_uuid(), 'CAPITAL_CASH', 'USD', NULL),
            (gen_random_uuid(), 'PAYMENT_CLEARING', 'USD', NULL)
    """))


def downgrade() -> None:
    op.drop_index('idx_ledger_entries_status', table_name='ledger_entries')
    op.drop_index('idx_ledger_entries_claim_id', table_name='ledger_entries')
    op.drop_index('idx_ledger_entries_related', table_name='ledger_entries')
    op.drop_index('idx_ledger_entries_account_id', table_name='ledger_entries')
    op.drop_table('ledger_entries')

    op.drop_index('idx_payment_intents_status', table_name='payment_intents')
    op.drop_index('idx_payment_intents_practice_id', table_name='payment_intents')
    op.drop_index('idx_payment_intents_claim_id', table_name='payment_intents')
    op.drop_table('payment_intents')

    op.drop_index('idx_ledger_accounts_practice_id', table_name='ledger_accounts')
    op.drop_index('idx_ledger_accounts_type', table_name='ledger_accounts')
    op.drop_table('ledger_accounts')

    op.drop_column('claims', 'exception_code')
    op.drop_column('claims', 'payment_exception')
