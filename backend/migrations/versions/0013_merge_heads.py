"""Merge the performance and learning/notification branches.

Revision ID: 0013_merge_heads
Revises: 0012_performance_goals, 0012_learning_notifications
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013_merge_heads"
down_revision = ("0012_performance_goals", "0012_learning_notifications")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both branches only add new tables; nothing to merge structurally.
    pass


def downgrade() -> None:
    pass
