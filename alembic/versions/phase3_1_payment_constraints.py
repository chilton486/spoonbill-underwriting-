"""Phase 3.1: Add amount_cents check constraint to payment_intents

Revision ID: phase3_1_payment_constraints
Revises: phase3_1_claim_token
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'phase3_1_payment_constraints'
down_revision: Union[str, None] = 'phase3_1_claim_token'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add amount_cents > 0 check constraint to payment_intents
    op.create_check_constraint(
        'ck_payment_intent_amount_positive',
        'payment_intents',
        'amount_cents > 0'
    )


def downgrade() -> None:
    op.drop_constraint('ck_payment_intent_amount_positive', 'payment_intents', type_='check')
