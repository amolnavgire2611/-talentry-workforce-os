"""Backfill organization membership without changing legacy roles."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_organization_memberships"
down_revision = "0007_employee_profile_details"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "organization_memberships" not in set(inspect(bind).get_table_names()):
        op.create_table(
            "organization_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(30), nullable=False),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
        )
        op.create_index("ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"])
        op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
        op.create_index("ix_organization_memberships_department_id", "organization_memberships", ["department_id"])

    bind.execute(sa.text(
        "INSERT INTO organization_memberships "
        "(organization_id, user_id, role, department_id, active) "
        "SELECT users.organization_id, users.id, users.role, users.department_id, users.active "
        "FROM users WHERE users.organization_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM organization_memberships AS memberships "
        "WHERE memberships.organization_id = users.organization_id AND memberships.user_id = users.id)"
    ))


def downgrade():
    # Forward-only so an assigned role cannot be lost through migration rollback.
    pass
