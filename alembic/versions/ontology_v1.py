"""Add ontology tables and practice funding_limit

Revision ID: ontology_v1
Revises: 264abc46ed87
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ontology_v1"
down_revision = "264abc46ed87"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practices", sa.Column("funding_limit_cents", sa.BigInteger(), nullable=True))

    op.create_table(
        "ontology_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("object_type", sa.String(50), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=True),
        sa.Column("properties_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ontology_objects_practice_type", "ontology_objects", ["practice_id", "object_type"])
    op.create_index("idx_ontology_objects_practice_key", "ontology_objects", ["practice_id", "object_key"])

    op.create_table(
        "ontology_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("link_type", sa.String(50), nullable=False),
        sa.Column("from_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ontology_objects.id"), nullable=False),
        sa.Column("to_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ontology_objects.id"), nullable=False),
        sa.Column("properties_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ontology_links_practice_type", "ontology_links", ["practice_id", "link_type"])
    op.create_index("idx_ontology_links_from", "ontology_links", ["from_object_id"])
    op.create_index("idx_ontology_links_to", "ontology_links", ["to_object_id"])

    op.create_table(
        "kpi_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Numeric(), nullable=True),
        sa.Column("as_of_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("provenance_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_kpi_observations_practice_metric", "kpi_observations", ["practice_id", "metric_name"])
    op.create_index("idx_kpi_observations_date", "kpi_observations", ["as_of_date"])


def downgrade() -> None:
    op.drop_table("kpi_observations")
    op.drop_table("ontology_links")
    op.drop_table("ontology_objects")
    op.drop_column("practices", "funding_limit_cents")
