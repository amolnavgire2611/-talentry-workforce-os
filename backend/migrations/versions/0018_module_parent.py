"""Add parent_id to modules for tree structure.

Revision ID: 0018_module_parent
Revises: 0017_password_history
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_module_parent"
down_revision = "0017_password_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("modules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_modules_parent_id",
            "modules",
            ["parent_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(batch_op.f("ix_modules_parent_id"), ["parent_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("modules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_modules_parent_id"))
        batch_op.drop_constraint("fk_modules_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")
