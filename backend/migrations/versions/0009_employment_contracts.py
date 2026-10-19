"""Add private employment contract metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_employment_contracts"
down_revision = "0008_organization_memberships"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "employment_contracts" in set(inspect(bind).get_table_names()):
        return
    op.create_table(
        "employment_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False),
        sa.Column("employment_type", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="Draft"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "employee_id", "reference", name="uq_contracts_org_employee_reference"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_contracts_end_after_start"),
    )
    op.create_index("ix_employment_contracts_organization_id", "employment_contracts", ["organization_id"])
    op.create_index("ix_employment_contracts_employee_id", "employment_contracts", ["employee_id"])
    op.create_index("ix_employment_contracts_start_date", "employment_contracts", ["start_date"])
    op.create_index("ix_employment_contracts_status", "employment_contracts", ["status"])
    op.create_index("ix_employment_contracts_created_by", "employment_contracts", ["created_by"])


def downgrade():
    # Forward-only to preserve signed-contract metadata and its audit trail.
    pass
