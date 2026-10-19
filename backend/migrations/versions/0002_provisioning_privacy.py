"""Add secure invitations, token revocation, and account/employee scope links.

This revision is intentionally additive and safe for databases already at 0001.
SQLite legacy tables gain nullable integer links without rebuilding the existing
users/employees tables; those links are validated in the service layer.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_provisioning_privacy"
down_revision = "0001_additive_foundation"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables or "employees" not in tables:
        raise RuntimeError("Apply the initial foundation migration before provisioning privacy migration.")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    employee_columns = {column["name"] for column in inspector.get_columns("employees")}
    is_sqlite = bind.dialect.name == "sqlite"
    if "department_id" not in user_columns:
        constraints = [] if is_sqlite else [sa.ForeignKey("departments.id", ondelete="SET NULL")]
        op.add_column("users", sa.Column("department_id", sa.Integer(), *constraints, nullable=True))
    if "user_id" not in employee_columns:
        constraints = [] if is_sqlite else [sa.ForeignKey("users.id", ondelete="SET NULL")]
        op.add_column("employees", sa.Column("user_id", sa.Integer(), *constraints, nullable=True))

    tables = set(inspect(bind).get_table_names())
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

    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("UPDATE users SET role = 'HR Administrator' WHERE role = 'HR Admin'"))
    else:
        bind.execute(sa.text("UPDATE users SET role = 'HR Administrator' WHERE role = 'HR Admin'"))

    existing_indexes = {}
    for table in ("users", "employees", "invitations", "revoked_tokens"):
        if table in inspect(bind).get_table_names():
            if bind.dialect.name == "sqlite":
                existing_indexes[table] = {row[0] for row in bind.execute(
                    sa.text("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = :table"),
                    {"table": table},
                )}
            else:
                existing_indexes[table] = {index["name"] for index in inspect(bind).get_indexes(table)}
    for table, name, columns, unique in (
        ("users", "ix_users_department_id", ["department_id"], False),
        ("employees", "ix_employees_user_id", ["user_id"], True),
        ("invitations", "ix_invitations_token_hash", ["token_hash"], True),
        ("revoked_tokens", "ix_revoked_tokens_expires_at", ["expires_at"], False),
        ("revoked_tokens", "ix_revoked_tokens_user_id", ["user_id"], False),
    ):
        if name not in existing_indexes.get(table, set()):
            op.create_index(name, table, columns, unique=unique)


def downgrade():
    # Forward-only: keep account links, invitation history, and revocation state.
    pass
