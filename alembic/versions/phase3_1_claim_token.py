"""Phase 3.1: Add claim_token column with backfill

Revision ID: phase3_1_claim_token
Revises: phase3_payments
Create Date: 2026-02-07

"""
from typing import Sequence, Union
import secrets
import base64

from alembic import op
import sqlalchemy as sa


revision: str = 'phase3_1_claim_token'
down_revision: Union[str, None] = 'phase3_payments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_claim_token() -> str:
    """Generate a unique, non-guessable claim token."""
    random_bytes = secrets.token_bytes(5)
    token_chars = base64.b32encode(random_bytes).decode('ascii')[:8]
    return f"SB-CLM-{token_chars}"


def upgrade() -> None:
    # Add claim_token column as nullable first
    op.add_column('claims', sa.Column('claim_token', sa.String(length=20), nullable=True))
    
    # Backfill existing claims with unique tokens
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM claims WHERE claim_token IS NULL"))
    claims = result.fetchall()
    
    for (claim_id,) in claims:
        token = generate_claim_token()
        # Ensure uniqueness by retrying if collision (unlikely but safe)
        for _ in range(10):
            existing = conn.execute(
                sa.text("SELECT 1 FROM claims WHERE claim_token = :token"),
                {"token": token}
            ).fetchone()
            if not existing:
                break
            token = generate_claim_token()
        
        conn.execute(
            sa.text("UPDATE claims SET claim_token = :token WHERE id = :id"),
            {"token": token, "id": claim_id}
        )
    
    # Now make the column NOT NULL and add unique constraint + index
    op.alter_column('claims', 'claim_token', nullable=False)
    op.create_unique_constraint('uq_claims_claim_token', 'claims', ['claim_token'])
    op.create_index('idx_claims_claim_token', 'claims', ['claim_token'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_claims_claim_token', table_name='claims')
    op.drop_constraint('uq_claims_claim_token', 'claims', type_='unique')
    op.drop_column('claims', 'claim_token')
