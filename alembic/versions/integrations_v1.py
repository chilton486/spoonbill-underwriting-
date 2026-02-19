"""Integrations v1: integration_connections, integration_sync_runs, claims.external_source

Revision ID: integrations_v1
Revises: ontology_v2
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa

revision = "integrations_v1"
down_revision = "ontology_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="OPEN_DENTAL"),
        sa.Column("status", sa.String(50), nullable=False, server_default="INACTIVE"),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("secrets_ref", sa.String(255), nullable=True),
        sa.Column("last_cursor", sa.String(255), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ic_practice_provider", "integration_connections", ["practice_id", "provider"], unique=True)

    op.create_table(
        "integration_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("integration_connections.id"), nullable=False),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="RUNNING"),
        sa.Column("pulled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("sync_type", sa.String(50), nullable=False, server_default="API"),
    )
    op.create_index("idx_isr_practice", "integration_sync_runs", ["practice_id"])
    op.create_index("idx_isr_connection", "integration_sync_runs", ["connection_id"])

    op.add_column("claims", sa.Column("external_source", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("claims", "external_source")
    op.drop_table("integration_sync_runs")
    op.drop_table("integration_connections")
