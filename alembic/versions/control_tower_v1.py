"""control tower: ops_tasks, external_balance_snapshots, external_payment_confirmations

Revision ID: control_tower_v1
Revises: integrations_v1
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "control_tower_v1"
down_revision = "integrations_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ops_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("playbook_type", sa.String(50), nullable=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=True),
        sa.Column("payment_intent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ops_tasks_status", "ops_tasks", ["status"])
    op.create_index("idx_ops_tasks_practice", "ops_tasks", ["practice_id", "status"])
    op.create_index("idx_ops_tasks_due", "ops_tasks", ["due_at"])

    op.create_table(
        "external_balance_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("facility", sa.String(100), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ext_balance_facility", "external_balance_snapshots", ["facility", "as_of"])

    op.create_table(
        "external_payment_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payment_intent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_intents.id"), nullable=False),
        sa.Column("rail_ref", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("resolved", sa.String(10), nullable=False, server_default="false"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ext_pay_confirm_pi", "external_payment_confirmations", ["payment_intent_id"])
    op.create_index("idx_ext_pay_confirm_status", "external_payment_confirmations", ["status"])


def downgrade() -> None:
    op.drop_table("external_payment_confirmations")
    op.drop_table("external_balance_snapshots")
    op.drop_table("ops_tasks")
