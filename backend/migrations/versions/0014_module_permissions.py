"""Add module-based role permissions.

Revision ID: 0014_module_permissions
Revises: 0013_merge_heads
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0014_module_permissions"
down_revision = "0013_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("module_key", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "module_key", name="uq_modules_org_module_key"),
    )
    op.create_index(op.f("ix_modules_module_key"), "modules", ["module_key"], unique=False)
    op.create_index(op.f("ix_modules_id"), "modules", ["id"], unique=False)

    op.create_table(
        "role_module_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "module_id", "role", name="uq_role_module_permissions_org_module_role"),
    )
    op.create_index(op.f("ix_role_module_permissions_id"), "role_module_permissions", ["id"], unique=False)
    op.create_index(op.f("ix_role_module_permissions_role"), "role_module_permissions", ["role"], unique=False)


def downgrade() -> None:
    op.drop_table("role_module_permissions")
    op.drop_table("modules")