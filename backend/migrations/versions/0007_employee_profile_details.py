"""Add private contacts and append-only employment snapshots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_employee_profile_details"
down_revision = "0006_organization_catalogs"
branch_labels = None
depends_on = None


def _create_if_missing(bind, table, columns, constraints=()):
    if table in set(inspect(bind).get_table_names()):
        return
    op.create_table(table, *columns, *constraints)
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def upgrade():
    bind = op.get_bind()
    _create_if_missing(bind, "employee_contacts", [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("personal_email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("alternate_phone", sa.String(30), nullable=True),
        sa.Column("address_line", sa.String(250), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(30), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", name="uq_employee_contacts_employee"),
    ])
    _create_if_missing(bind, "emergency_contacts", [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("relationship", sa.String(60), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ])
    if "emergency_contacts" in set(inspect(bind).get_table_names()):
        columns = {column["name"] for column in inspect(bind).get_columns("emergency_contacts")}
        if "employee_id" in columns:
            indexes = {index["name"] for index in inspect(bind).get_indexes("emergency_contacts")}
            if "ix_emergency_contacts_employee_id" not in indexes:
                op.create_index("ix_emergency_contacts_employee_id", "emergency_contacts", ["employee_id"])

    _create_if_missing(bind, "employee_employment_history", [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("job_title", sa.String(100), nullable=False),
        sa.Column("branch_name", sa.String(100), nullable=True),
        sa.Column("designation_name", sa.String(100), nullable=True),
        sa.Column("grade_name", sa.String(100), nullable=True),
        sa.Column("reporting_manager_name", sa.String(100), nullable=True),
        sa.Column("employment_status", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ])
    for table, column in (("employee_contacts", "employee_id"), ("employee_employment_history", "employee_id"),
                          ("employee_employment_history", "effective_date"), ("employee_employment_history", "created_by")):
        indexes = {index["name"] for index in inspect(bind).get_indexes(table)}
        index_name = f"ix_{table}_{column}"
        if index_name not in indexes:
            op.create_index(index_name, table, [column])


def downgrade():
    # Forward-only to preserve employee and audit history.
    pass
