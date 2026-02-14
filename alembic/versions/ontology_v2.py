"""Ontology Phase 2: metric_timeseries table + link_type expansion

Revision ID: ontology_v2
Revises: ontology_v1
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ontology_v2"
down_revision = "ontology_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_timeseries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_metric_ts_practice_metric_date", "metric_timeseries", ["practice_id", "metric_name", "date"])
    op.create_index("idx_metric_ts_practice_date", "metric_timeseries", ["practice_id", "date"])

    op.execute("ALTER TABLE ontology_objects ALTER COLUMN object_type TYPE VARCHAR(100)")
    op.execute("ALTER TABLE ontology_links ALTER COLUMN link_type TYPE VARCHAR(100)")


def downgrade() -> None:
    op.execute("ALTER TABLE ontology_links ALTER COLUMN link_type TYPE VARCHAR(50)")
    op.execute("ALTER TABLE ontology_objects ALTER COLUMN object_type TYPE VARCHAR(50)")
    op.drop_table("metric_timeseries")
