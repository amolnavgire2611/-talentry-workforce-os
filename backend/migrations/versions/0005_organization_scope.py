"""Assign existing Nexora data to one organization and scope tenant records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_organization_scope"
down_revision = "0004_refresh_sessions"
branch_labels = None
depends_on = None


TENANT_TABLES = (
    "users",
    "employees",
    "departments",
    "invitations",
    "revoked_tokens",
    "refresh_sessions",
    "attendance",
    "leave_requests",
    "leave_types",
    "leave_balances",
    "holidays",
    "audit_logs",
)
GLOBAL_UNIQUES_TO_SCOPE = {
    "employees": "employee_code",
    "departments": "name",
    "leave_types": "name",
    "holidays": "holiday_date",
}
GLOBAL_EXPRESSION_INDEXES = {
    "departments": "uq_departments_name_normalized",
    "leave_types": "uq_leave_types_name_normalized",
}


def upgrade():
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    if "organizations" not in existing_tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(80), nullable=False, unique=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    organizations = bind.execute(sa.text("SELECT id FROM organizations WHERE slug = 'nexora'")).first()
    if organizations is None:
        bind.execute(sa.text(
            "INSERT INTO organizations (name, slug, active) VALUES ('NEXORA', 'nexora', 1)"
        ))
        organization_id = bind.execute(sa.text(
            "SELECT id FROM organizations WHERE slug = 'nexora'"
        )).scalar_one()
    else:
        organization_id = organizations[0]

    for table in TENANT_TABLES:
        columns = {column["name"] for column in inspect(bind).get_columns(table)}
        if "organization_id" not in columns:
            op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        bind.execute(sa.text(
            f"UPDATE {table} SET organization_id = :organization_id WHERE organization_id IS NULL"
        ), {"organization_id": organization_id})

        unique_column = GLOBAL_UNIQUES_TO_SCOPE.get(table)
        old_constraints = []
        if unique_column:
            for index in inspect(bind).get_indexes(table):
                if index.get("unique") and index.get("column_names") == [unique_column]:
                    if bind.dialect.name == "sqlite":
                        bind.execute(sa.text(f"DROP INDEX IF EXISTS {index['name']}"))
                    else:
                        op.drop_index(index["name"], table_name=table)
            for index_name in (GLOBAL_EXPRESSION_INDEXES.get(table),):
                if index_name:
                    bind.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
            old_constraints = [constraint for constraint in inspect(bind).get_unique_constraints(table)
                               if constraint.get("column_names") == [unique_column]]

        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(
                table, recreate="always",
                naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
            ) as batch:
                for constraint in old_constraints:
                    constraint_name = constraint.get("name") or f"uq_{table}_{unique_column}"
                    batch.drop_constraint(constraint_name, type_="unique")
                batch.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
                batch.create_foreign_key(
                    f"fk_{table}_organization_id_organizations",
                    "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
                )
                if table == "employees":
                    batch.create_unique_constraint(
                        "uq_employees_org_employee_code", ["organization_id", "employee_code"],
                    )
                elif table == "holidays":
                    batch.create_unique_constraint("uq_holidays_org_date", ["organization_id", "holiday_date"])
        else:
            for constraint in old_constraints:
                if constraint.get("name"):
                    op.drop_constraint(constraint["name"], table, type_="unique")
            op.alter_column(table, "organization_id", existing_type=sa.Integer(), nullable=False)
            op.create_foreign_key(
                f"fk_{table}_organization_id_organizations",
                table, "organizations", ["organization_id"], ["id"], ondelete="RESTRICT",
            )
            if table == "employees":
                op.create_unique_constraint("uq_employees_org_employee_code", table, ["organization_id", "employee_code"])
            elif table == "holidays":
                op.create_unique_constraint("uq_holidays_org_date", table, ["organization_id", "holiday_date"])
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    # SQLite batch table rebuilds do not reliably retain expression indexes.
    op.create_index("uq_users_email_normalized", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_departments_org_name_normalized", "departments",
                    ["organization_id", sa.text("lower(name)")], unique=True)
    op.create_index("uq_leave_types_org_name_normalized", "leave_types",
                    ["organization_id", sa.text("lower(name)")], unique=True)


def downgrade():
    # Forward-only: the migration assigns every existing record to an organization.
    pass
