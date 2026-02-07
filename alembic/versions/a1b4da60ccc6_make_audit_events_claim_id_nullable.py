"""make_audit_events_claim_id_nullable

Revision ID: a1b4da60ccc6
Revises: practice_applications
Create Date: 2026-02-07 16:31:43.540804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b4da60ccc6'
down_revision: Union[str, None] = 'practice_applications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make claim_id nullable to support non-claim audit events (e.g., application approval)
    op.alter_column('audit_events', 'claim_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    # Revert claim_id to NOT NULL (will fail if there are NULL values)
    op.alter_column('audit_events', 'claim_id',
                    existing_type=sa.Integer(),
                    nullable=False)
