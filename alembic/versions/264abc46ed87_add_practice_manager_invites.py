"""add_practice_manager_invites

Revision ID: 264abc46ed87
Revises: a1b4da60ccc6
Create Date: 2026-02-07 16:45:01.536307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '264abc46ed87'
down_revision: Union[str, None] = 'a1b4da60ccc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'practice_manager_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_practice_manager_invites_id'), 'practice_manager_invites', ['id'], unique=False)
    op.create_index(op.f('ix_practice_manager_invites_user_id'), 'practice_manager_invites', ['user_id'], unique=False)
    op.create_index(op.f('ix_practice_manager_invites_token'), 'practice_manager_invites', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_practice_manager_invites_token'), table_name='practice_manager_invites')
    op.drop_index(op.f('ix_practice_manager_invites_user_id'), table_name='practice_manager_invites')
    op.drop_index(op.f('ix_practice_manager_invites_id'), table_name='practice_manager_invites')
    op.drop_table('practice_manager_invites')
