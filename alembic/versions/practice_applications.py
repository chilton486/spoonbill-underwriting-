"""Add practice_applications table for onboarding intake

Revision ID: practice_applications
Revises: phase3_1_payment_constraints
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'practice_applications'
down_revision = 'phase3_1_payment_constraints'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'practice_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        # Practice Information
        sa.Column('legal_name', sa.String(255), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('phone', sa.String(50), nullable=False),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('tax_id', sa.String(50), nullable=True),
        sa.Column('practice_type', sa.String(50), nullable=False),
        # Practice Size & Operations
        sa.Column('years_in_operation', sa.Integer(), nullable=False),
        sa.Column('provider_count', sa.Integer(), nullable=False),
        sa.Column('operatory_count', sa.Integer(), nullable=False),
        # Financial Information
        sa.Column('avg_monthly_collections_range', sa.String(100), nullable=False),
        sa.Column('insurance_vs_self_pay_mix', sa.String(100), nullable=False),
        sa.Column('top_payers', sa.Text(), nullable=True),
        sa.Column('avg_ar_days', sa.Integer(), nullable=True),
        # Billing Operations
        sa.Column('billing_model', sa.String(50), nullable=False),
        sa.Column('follow_up_frequency', sa.String(100), nullable=True),
        sa.Column('practice_management_software', sa.String(100), nullable=True),
        sa.Column('claims_per_month', sa.Integer(), nullable=True),
        sa.Column('electronic_claims', sa.Boolean(), nullable=True, default=True),
        # Application Details
        sa.Column('stated_goal', sa.Text(), nullable=True),
        sa.Column('urgency_level', sa.String(50), nullable=False, server_default='MEDIUM'),
        # Contact Information
        sa.Column('contact_name', sa.String(255), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=False),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        # Status & Tracking
        sa.Column('status', sa.String(50), nullable=False, server_default='SUBMITTED'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        # Link to created practice
        sa.Column('created_practice_id', sa.Integer(), nullable=True),
        # Primary key and foreign keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_practice_id'], ['practices.id']),
    )
    
    # Create indexes
    op.create_index('ix_practice_applications_id', 'practice_applications', ['id'])
    op.create_index('ix_practice_applications_status', 'practice_applications', ['status'])
    op.create_index('ix_practice_applications_contact_email', 'practice_applications', ['contact_email'])


def downgrade() -> None:
    op.drop_index('ix_practice_applications_contact_email', 'practice_applications')
    op.drop_index('ix_practice_applications_status', 'practice_applications')
    op.drop_index('ix_practice_applications_id', 'practice_applications')
    op.drop_table('practice_applications')
