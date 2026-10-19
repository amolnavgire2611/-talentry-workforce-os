"""Add branches, designations, job grades, and employee assignments."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_organization_catalogs"
down_revision = "0005_organization_scope"
branch_labels = None
depends_on = None


def _create_tenant_index(table):
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def upgrade():
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "branches" not in tables:
        op.create_table(
            "branches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("code", sa.String(30), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("address", sa.String(300), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),
        )
        _create_tenant_index("branches")
        op.create_index("ix_branches_code", "branches", ["code"])
        op.create_index("ix_branches_name", "branches", ["name"])
        op.create_index("uq_branches_org_name_normalized", "branches",
                        ["organization_id", sa.text("lower(name)")], unique=True)

    if "designations" not in tables:
        op.create_table(
            "designations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        _create_tenant_index("designations")
        op.create_index("ix_designations_name", "designations", ["name"])
        op.create_index("uq_designations_org_name_normalized", "designations",
                        ["organization_id", sa.text("lower(name)")], unique=True)

    if "job_grades" not in tables:
        op.create_table(
            "job_grades",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("code", sa.String(30), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("organization_id", "code", name="uq_job_grades_org_code"),
        )
        _create_tenant_index("job_grades")
        op.create_index("ix_job_grades_code", "job_grades", ["code"])
        op.create_index("ix_job_grades_name", "job_grades", ["name"])
        op.create_index("uq_job_grades_org_name_normalized", "job_grades",
                        ["organization_id", sa.text("lower(name)")], unique=True)

    employee_columns = {column["name"] for column in inspect(bind).get_columns("employees")}
    new_assignments = {
        "branch_id": ("branches", "SET NULL"),
        "designation_id": ("designations", "SET NULL"),
        "job_grade_id": ("job_grades", "SET NULL"),
        "reporting_manager_id": ("employees", "SET NULL"),
    }
    missing = {name: target for name, target in new_assignments.items() if name not in employee_columns}
    if missing and bind.dialect.name == "sqlite":
        with op.batch_alter_table("employees", recreate="always") as batch:
            for name, (target, ondelete) in missing.items():
                batch.add_column(sa.Column(name, sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    f"fk_employees_{name}_{target}", target, [name], ["id"], ondelete=ondelete,
                )
                batch.create_index(f"ix_employees_{name}", [name])
    else:
        for name, (target, ondelete) in missing.items():
            op.add_column("employees", sa.Column(
                name, sa.Integer(), sa.ForeignKey(f"{target}.id", ondelete=ondelete), nullable=True,
            ))
            op.create_index(f"ix_employees_{name}", "employees", [name])


def downgrade():
    # Forward-only; assignments are historical HR data once populated.
    pass
