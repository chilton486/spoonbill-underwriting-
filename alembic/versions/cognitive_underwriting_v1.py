"""cognitive underwriting v1 - add underwriting_runs table for LLM audit trail

Revision ID: cognitive_underwriting_v1
Revises: ontology_expansion_v1
Create Date: 2026-03-07

Adds:
- underwriting_runs table for persisting LLM-assisted underwriting decisions
  with full audit trail: model, prompt version, input hash, output, latency,
  fallback status, and merged recommendation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "cognitive_underwriting_v1"
down_revision = "ontology_expansion_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "underwriting_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),

        # Model/provider info
        sa.Column("model_provider", sa.String(50), nullable=False, server_default="anthropic"),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),

        # Input audit
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("input_snapshot_json", postgresql.JSONB(), nullable=True),

        # Output
        sa.Column("output_json", postgresql.JSONB(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),

        # Decision fields
        sa.Column("recommendation", sa.String(50), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),

        # Merge result
        sa.Column("deterministic_recommendation", sa.String(50), nullable=True),
        sa.Column("merged_recommendation", sa.String(50), nullable=True),

        # Run metadata
        sa.Column("run_type", sa.String(50), nullable=False, server_default="underwrite_claim"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("parse_success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),

        # Review
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewer_override", sa.String(50), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_uw_runs_claim_id", "underwriting_runs", ["claim_id"])
    op.create_index("idx_uw_runs_practice_id", "underwriting_runs", ["practice_id"])
    op.create_index("idx_uw_runs_run_type", "underwriting_runs", ["run_type"])
    op.create_index("idx_uw_runs_created_at", "underwriting_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_uw_runs_created_at", "underwriting_runs")
    op.drop_index("idx_uw_runs_run_type", "underwriting_runs")
    op.drop_index("idx_uw_runs_practice_id", "underwriting_runs")
    op.drop_index("idx_uw_runs_claim_id", "underwriting_runs")
    op.drop_table("underwriting_runs")
