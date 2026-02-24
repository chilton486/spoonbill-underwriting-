"""Intake revamp: structured underwriting fields + score columns

Revision ID: intake_revamp_v1
Revises: control_tower_v1
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = "intake_revamp_v1"
down_revision = "control_tower_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("practice_applications") as batch_op:
        batch_op.add_column(sa.Column("dba", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("ein", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("npi_individual", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("npi_group", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("ownership_structure", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("prior_bankruptcy", sa.Boolean(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("pending_litigation", sa.Boolean(), nullable=True, server_default="0"))

        batch_op.add_column(sa.Column("gross_production_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("net_collections_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("insurance_collections_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("patient_collections_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("seasonality_swings", sa.Boolean(), nullable=True, server_default="0"))

        batch_op.add_column(sa.Column("top_payers_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pct_ppo", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pct_medicaid", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pct_ffs", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pct_capitation", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("avg_claim_size_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("avg_monthly_claim_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("avg_days_to_reimbursement", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_denial_rate", sa.Float(), nullable=True))

        batch_op.add_column(sa.Column("billing_staff_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("dedicated_rcm_manager", sa.Boolean(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("written_billing_sop", sa.Boolean(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("outstanding_ar_balance_cents", sa.Integer(), nullable=True))

        batch_op.add_column(sa.Column("primary_bank", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("cash_on_hand_range", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("existing_loc_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("monthly_debt_payments_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("missed_loan_payments_24m", sa.Boolean(), nullable=True, server_default="0"))

        batch_op.add_column(sa.Column("desired_funding_cadence", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("expected_monthly_funding_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("urgency_scale", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("willing_to_integrate_api", sa.Boolean(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("why_spoonbill", sa.Text(), nullable=True))

        batch_op.add_column(sa.Column("underwriting_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("underwriting_grade", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("underwriting_breakdown_json", sa.Text(), nullable=True))

        batch_op.alter_column("address", nullable=True)
        batch_op.alter_column("phone", nullable=True)
        batch_op.alter_column("practice_type", nullable=True)
        batch_op.alter_column("provider_count", nullable=True)
        batch_op.alter_column("operatory_count", nullable=True)
        batch_op.alter_column("avg_monthly_collections_range", nullable=True)
        batch_op.alter_column("insurance_vs_self_pay_mix", nullable=True)
        batch_op.alter_column("urgency_level", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("practice_applications") as batch_op:
        batch_op.drop_column("underwriting_breakdown_json")
        batch_op.drop_column("underwriting_grade")
        batch_op.drop_column("underwriting_score")
        batch_op.drop_column("why_spoonbill")
        batch_op.drop_column("willing_to_integrate_api")
        batch_op.drop_column("urgency_scale")
        batch_op.drop_column("expected_monthly_funding_cents")
        batch_op.drop_column("desired_funding_cadence")
        batch_op.drop_column("missed_loan_payments_24m")
        batch_op.drop_column("monthly_debt_payments_cents")
        batch_op.drop_column("existing_loc_cents")
        batch_op.drop_column("cash_on_hand_range")
        batch_op.drop_column("primary_bank")
        batch_op.drop_column("outstanding_ar_balance_cents")
        batch_op.drop_column("written_billing_sop")
        batch_op.drop_column("dedicated_rcm_manager")
        batch_op.drop_column("billing_staff_count")
        batch_op.drop_column("estimated_denial_rate")
        batch_op.drop_column("avg_days_to_reimbursement")
        batch_op.drop_column("avg_monthly_claim_count")
        batch_op.drop_column("avg_claim_size_cents")
        batch_op.drop_column("pct_capitation")
        batch_op.drop_column("pct_ffs")
        batch_op.drop_column("pct_medicaid")
        batch_op.drop_column("pct_ppo")
        batch_op.drop_column("top_payers_json")
        batch_op.drop_column("seasonality_swings")
        batch_op.drop_column("patient_collections_cents")
        batch_op.drop_column("insurance_collections_cents")
        batch_op.drop_column("net_collections_cents")
        batch_op.drop_column("gross_production_cents")
        batch_op.drop_column("pending_litigation")
        batch_op.drop_column("prior_bankruptcy")
        batch_op.drop_column("ownership_structure")
        batch_op.drop_column("npi_group")
        batch_op.drop_column("npi_individual")
        batch_op.drop_column("ein")
        batch_op.drop_column("dba")
