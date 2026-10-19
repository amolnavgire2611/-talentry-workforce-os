"""Merge module permissions with employment contracts branch.

Revision ID: 0015_merge_module_permissions
Revises: 0009_employment_contracts, 0014_module_permissions
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015_merge_module_permissions"
down_revision = ("0009_employment_contracts", "0014_module_permissions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both branches only add new tables; nothing to merge structurally.
    pass


def downgrade() -> None:
    pass