"""Add roles, workforce workflows, and audit records without replacing legacy tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_additive_foundation"
down_revision = None
branch_labels = None
depends_on = None


def _table_names():
    return set(inspect(op.get_bind()).get_table_names())


def _create_index_if_missing(name, table, columns, unique=False):
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        existing = {row[0] for row in bind.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = :table"),
            {"table": table},
        )}
    else:
        existing = {index["name"] for index in inspect(bind).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=unique)


def _create_legacy_tables_if_missing(tables):
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("role", sa.String(30), nullable=False, server_default="Employee"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "employees" not in tables:
        op.create_table(
            "employees",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("department", sa.String(100), nullable=False),
            sa.Column("role", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        )


def upgrade():
    tables = _table_names()
    _create_legacy_tables_if_missing(tables)
    tables = _table_names()
    user_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    department_fk = [] if op.get_bind().dialect.name == "sqlite" else [sa.ForeignKey("departments.id", ondelete="SET NULL")]
    if "role" not in user_columns:
        op.add_column("users", sa.Column("role", sa.String(30), nullable=False, server_default="Employee"))
    if "active" not in user_columns:
        op.add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))

    if "departments" not in tables:
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if "department_id" not in user_columns:
        op.add_column("users", sa.Column("department_id", sa.Integer(), *department_fk, nullable=True))
    employee_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("employees")}
    if "user_id" not in employee_columns:
        employee_fk = [] if op.get_bind().dialect.name == "sqlite" else [sa.ForeignKey("users.id", ondelete="SET NULL")]
        op.add_column("employees", sa.Column("user_id", sa.Integer(), *employee_fk, nullable=True))
    if "attendance" not in tables:
        op.create_table(
            "attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("check_in", sa.DateTime(timezone=True), nullable=False),
            sa.Column("check_out", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="Present"),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "work_date", name="uq_attendance_user_date"),
        )
    if "leave_requests" not in tables:
        op.create_table(
            "leave_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.String(64), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if "invitations" not in tables:
        op.create_table(
            "invitations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "revoked_tokens" not in tables:
        op.create_table(
            "revoked_tokens",
            sa.Column("jti", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    # Normalize the role name used by the first iteration without upgrading it to Super Admin.
    op.get_bind().execute(sa.text("UPDATE users SET role = 'HR Administrator' WHERE role = 'HR Admin'"))

    # Refuse to discard conflicting legacy keys; the migration makes no data changes to these records.
    duplicates = op.get_bind().execute(sa.text(
        "SELECT lower(email) FROM users GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError("Cannot add normalized unique email index: resolve duplicate legacy emails first.")
    employee_duplicates = op.get_bind().execute(sa.text(
        "SELECT employee_code FROM employees GROUP BY employee_code HAVING count(*) > 1 LIMIT 1"
    )).first()
    if employee_duplicates:
        raise RuntimeError("Cannot add unique employee code index: resolve duplicate legacy employee codes first.")

    _create_index_if_missing("uq_users_email_normalized", "users", [sa.text("lower(email)")], unique=True)
    _create_index_if_missing("uq_employees_employee_code", "employees", ["employee_code"], unique=True)
    _create_index_if_missing("uq_departments_name_normalized", "departments", [sa.text("lower(name)")], unique=True)
    _create_index_if_missing("ix_employees_user_id", "employees", ["user_id"], unique=True)
    _create_index_if_missing("ix_users_department_id", "users", ["department_id"])
    _create_index_if_missing("ix_invitations_token_hash", "invitations", ["token_hash"], unique=True)
    _create_index_if_missing("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
    _create_index_if_missing("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])
    _create_index_if_missing("ix_attendance_user_date", "attendance", ["user_id", "work_date"])
    _create_index_if_missing("ix_leave_requests_user_status", "leave_requests", ["user_id", "status"])
    _create_index_if_missing("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    # This baseline is intentionally forward-only to guarantee legacy user and employee data is never dropped.
    pass