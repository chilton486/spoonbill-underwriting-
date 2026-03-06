"""ontology expansion v1 - add first-class ontology tables and enhance existing models

Revision ID: ontology_expansion_v1
Revises: ontology_v2
Create Date: 2026-03-06

Adds:
- providers table
- payers table
- payer_contracts table
- procedure_codes table
- claim_lines table
- funding_decisions table
- remittances table
- remittance_lines table
- fee_schedule_items table

Enhances:
- practices: add ontology fields (legal_name, ein, npi, address, pms_type, etc.)
- claims: add payer_id, provider_id, payer_contract_id FKs and additional fields
- payment_intents: add queued_at, failed_at, account refs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ontology_expansion_v1"
down_revision = "ontology_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New tables ---

    op.create_table(
        "providers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("npi", sa.String(20), nullable=True, index=True),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="ASSOCIATE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_providers_practice_active", "providers", ["practice_id", "is_active"])

    op.create_table(
        "payers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payer_code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan_types", postgresql.JSONB(), nullable=True),
        sa.Column("eft_capable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("era_capable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("filing_limit_days", sa.Integer(), nullable=True),
        sa.Column("contact_info", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_payers_name", "payers", ["name"])

    op.create_table(
        "payer_contracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("payers.id"), nullable=False, index=True),
        sa.Column("effective_start_date", sa.Date(), nullable=True),
        sa.Column("effective_end_date", sa.Date(), nullable=True),
        sa.Column("network_status", sa.String(50), nullable=False, server_default="IN_NETWORK"),
        sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
        sa.Column("annual_max_norms", postgresql.JSONB(), nullable=True),
        sa.Column("documentation_rules", postgresql.JSONB(), nullable=True),
        sa.Column("timely_filing_limit_days", sa.Integer(), nullable=True),
        sa.Column("cob_rules", sa.Text(), nullable=True),
        sa.Column("contract_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_payer_contracts_practice_payer", "payer_contracts", ["practice_id", "payer_id"])
    op.create_index("idx_payer_contracts_status", "payer_contracts", ["status"])

    op.create_table(
        "procedure_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cdt_code", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("short_description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="OTHER"),
        sa.Column("documentation_requirements", sa.Text(), nullable=True),
        sa.Column("common_denial_reasons", postgresql.JSONB(), nullable=True),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_procedure_codes_category", "procedure_codes", ["category"])

    op.create_table(
        "claim_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
        sa.Column("procedure_code_id", sa.Integer(), sa.ForeignKey("procedure_codes.id"), nullable=True, index=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=True, index=True),
        sa.Column("cdt_code", sa.String(10), nullable=True),
        sa.Column("tooth", sa.String(10), nullable=True),
        sa.Column("surface", sa.String(20), nullable=True),
        sa.Column("quadrant", sa.String(10), nullable=True),
        sa.Column("modifier", sa.String(50), nullable=True),
        sa.Column("billed_fee_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("allowed_fee_cents", sa.BigInteger(), nullable=True),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("line_status", sa.String(30), nullable=True, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_claim_lines_claim", "claim_lines", ["claim_id"])
    op.create_index("idx_claim_lines_procedure", "claim_lines", ["procedure_code_id"])

    op.create_table(
        "funding_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False, index=True),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("advance_rate", sa.Float(), nullable=True),
        sa.Column("max_advance_amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("fee_rate", sa.Float(), nullable=True),
        sa.Column("required_docs_flags", postgresql.JSONB(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("reasons_json", postgresql.JSONB(), nullable=True),
        sa.Column("decisioned_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("decisioned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("policy_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_funding_decisions_claim", "funding_decisions", ["claim_id"])
    op.create_index("idx_funding_decisions_decision", "funding_decisions", ["decision"])

    op.create_table(
        "remittances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("payers.id"), nullable=True, index=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id"), nullable=False, index=True),
        sa.Column("payer_name", sa.String(255), nullable=True),
        sa.Column("trace_number", sa.String(100), nullable=True, index=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("total_paid_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_adjustments_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("raw_file_ref", sa.String(500), nullable=True),
        sa.Column("posting_status", sa.String(30), nullable=False, server_default="RECEIVED"),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="SYNTHETIC"),
        sa.Column("era_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_remittances_practice", "remittances", ["practice_id"])
    op.create_index("idx_remittances_payer", "remittances", ["payer_id"])
    op.create_index("idx_remittances_status", "remittances", ["posting_status"])

    op.create_table(
        "remittance_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("remittance_id", sa.Integer(), sa.ForeignKey("remittances.id"), nullable=False, index=True),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=True, index=True),
        sa.Column("claim_line_id", sa.Integer(), sa.ForeignKey("claim_lines.id"), nullable=True, index=True),
        sa.Column("external_claim_id", sa.String(255), nullable=True),
        sa.Column("cdt_code", sa.String(10), nullable=True),
        sa.Column("paid_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("allowed_cents", sa.BigInteger(), nullable=True),
        sa.Column("adjustment_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("adjustment_reason_codes", postgresql.JSONB(), nullable=True),
        sa.Column("match_status", sa.String(30), nullable=False, server_default="UNMATCHED"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_remittance_lines_remittance", "remittance_lines", ["remittance_id"])
    op.create_index("idx_remittance_lines_claim", "remittance_lines", ["claim_id"])
    op.create_index("idx_remittance_lines_match", "remittance_lines", ["match_status"])

    op.create_table(
        "fee_schedule_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payer_contract_id", sa.Integer(), sa.ForeignKey("payer_contracts.id"), nullable=False, index=True),
        sa.Column("procedure_code_id", sa.Integer(), sa.ForeignKey("procedure_codes.id"), nullable=True, index=True),
        sa.Column("cdt_code", sa.String(10), nullable=False),
        sa.Column("allowed_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("effective_date", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_fee_schedule_contract_code", "fee_schedule_items", ["payer_contract_id", "cdt_code"])

    # --- Enhance practices ---
    op.add_column("practices", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("practices", sa.Column("legal_name", sa.String(255), nullable=True))
    op.add_column("practices", sa.Column("dba_name", sa.String(255), nullable=True))
    op.add_column("practices", sa.Column("ein", sa.String(20), nullable=True))
    op.add_column("practices", sa.Column("group_npi", sa.String(20), nullable=True))
    op.add_column("practices", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("practices", sa.Column("address_line2", sa.String(255), nullable=True))
    op.add_column("practices", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("practices", sa.Column("state", sa.String(50), nullable=True))
    op.add_column("practices", sa.Column("zip_code", sa.String(20), nullable=True))
    op.add_column("practices", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("practices", sa.Column("owners_metadata", postgresql.JSONB(), nullable=True))
    op.add_column("practices", sa.Column("bank_payout_profile", postgresql.JSONB(), nullable=True))
    op.add_column("practices", sa.Column("pms_type", sa.String(100), nullable=True))
    op.add_column("practices", sa.Column("clearinghouse", sa.String(100), nullable=True))

    # --- Enhance claims ---
    op.add_column("claims", sa.Column("payer_id", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("payer_contract_id", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("clearinghouse_control_number", sa.String(100), nullable=True))
    op.add_column("claims", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    op.add_column("claims", sa.Column("adjudicated_at", sa.DateTime(), nullable=True))
    op.add_column("claims", sa.Column("patient_responsibility_estimate", sa.BigInteger(), nullable=True))
    op.add_column("claims", sa.Column("total_billed_cents", sa.BigInteger(), nullable=True))
    op.add_column("claims", sa.Column("total_allowed_cents", sa.BigInteger(), nullable=True))
    op.add_column("claims", sa.Column("total_paid_cents", sa.BigInteger(), nullable=True))
    op.add_column("claims", sa.Column("source_system", sa.String(100), nullable=True))

    op.create_foreign_key("fk_claims_payer_id", "claims", "payers", ["payer_id"], ["id"])
    op.create_foreign_key("fk_claims_provider_id", "claims", "providers", ["provider_id"], ["id"])
    op.create_foreign_key("fk_claims_payer_contract_id", "claims", "payer_contracts", ["payer_contract_id"], ["id"])
    op.create_index("idx_claims_payer_id", "claims", ["payer_id"])
    op.create_index("idx_claims_status_practice", "claims", ["status", "practice_id"])

    # --- Enhance payment_intents ---
    op.add_column("payment_intents", sa.Column("queued_at", sa.DateTime(), nullable=True))
    op.add_column("payment_intents", sa.Column("failed_at", sa.DateTime(), nullable=True))
    op.add_column("payment_intents", sa.Column("funding_source_account_ref", sa.String(255), nullable=True))
    op.add_column("payment_intents", sa.Column("destination_account_ref", sa.String(255), nullable=True))


def downgrade() -> None:
    # Payment intent columns
    op.drop_column("payment_intents", "destination_account_ref")
    op.drop_column("payment_intents", "funding_source_account_ref")
    op.drop_column("payment_intents", "failed_at")
    op.drop_column("payment_intents", "queued_at")

    # Claims columns and FKs
    op.drop_index("idx_claims_status_practice", "claims")
    op.drop_index("idx_claims_payer_id", "claims")
    op.drop_constraint("fk_claims_payer_contract_id", "claims", type_="foreignkey")
    op.drop_constraint("fk_claims_provider_id", "claims", type_="foreignkey")
    op.drop_constraint("fk_claims_payer_id", "claims", type_="foreignkey")
    op.drop_column("claims", "source_system")
    op.drop_column("claims", "total_paid_cents")
    op.drop_column("claims", "total_allowed_cents")
    op.drop_column("claims", "total_billed_cents")
    op.drop_column("claims", "patient_responsibility_estimate")
    op.drop_column("claims", "adjudicated_at")
    op.drop_column("claims", "submitted_at")
    op.drop_column("claims", "clearinghouse_control_number")
    op.drop_column("claims", "payer_contract_id")
    op.drop_column("claims", "provider_id")
    op.drop_column("claims", "payer_id")

    # Practice columns
    op.drop_column("practices", "clearinghouse")
    op.drop_column("practices", "pms_type")
    op.drop_column("practices", "bank_payout_profile")
    op.drop_column("practices", "owners_metadata")
    op.drop_column("practices", "phone")
    op.drop_column("practices", "zip_code")
    op.drop_column("practices", "state")
    op.drop_column("practices", "city")
    op.drop_column("practices", "address_line2")
    op.drop_column("practices", "address_line1")
    op.drop_column("practices", "group_npi")
    op.drop_column("practices", "ein")
    op.drop_column("practices", "dba_name")
    op.drop_column("practices", "legal_name")
    op.drop_column("practices", "updated_at")

    # Drop new tables in reverse dependency order
    op.drop_table("fee_schedule_items")
    op.drop_table("remittance_lines")
    op.drop_table("remittances")
    op.drop_table("funding_decisions")
    op.drop_table("claim_lines")
    op.drop_table("procedure_codes")
    op.drop_table("payer_contracts")
    op.drop_table("payers")
    op.drop_table("providers")
