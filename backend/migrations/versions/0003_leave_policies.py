"""Add configurable leave types, annual balances, holiday calendar and request fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_leave_policies"
down_revision = "0002_provisioning_privacy"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "leave_types" not in tables:
        op.create_table(
            "leave_types",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("annual_allowance_days", sa.Integer(), nullable=False),
            sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("uq_leave_types_name_normalized", "leave_types", [sa.text("lower(name)")], unique=True)
    if "leave_balances" not in tables:
        op.create_table(
            "leave_balances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("allocated_days", sa.Integer(), nullable=False),
            sa.Column("used_days", sa.Numeric(7, 2), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "leave_type_id", "year", name="uq_leave_balance_user_type_year"),
            sa.CheckConstraint("allocated_days >= 0 AND used_days >= 0 AND used_days <= allocated_days", name="ck_leave_balance_range"),
        )
        op.create_index("ix_leave_balances_user_id", "leave_balances", ["user_id"])
        op.create_index("ix_leave_balances_year", "leave_balances", ["year"])
    if "holidays" not in tables:
        op.create_table(
            "holidays",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("holiday_date", sa.Date(), nullable=False, unique=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_holidays_holiday_date", "holidays", ["holiday_date"])

    leave_columns = {column["name"] for column in inspect(bind).get_columns("leave_requests")}
    if "leave_type_id" not in leave_columns:
        constraints = [] if bind.dialect.name == "sqlite" else [sa.ForeignKey("leave_types.id", ondelete="RESTRICT")]
        op.add_column("leave_requests", sa.Column("leave_type_id", sa.Integer(), *constraints, nullable=True))
    if "half_day" not in leave_columns:
        op.add_column("leave_requests", sa.Column("half_day", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "days_requested" not in leave_columns:
        op.add_column("leave_requests", sa.Column("days_requested", sa.Numeric(7, 2), nullable=False, server_default="1"))
    if "review_comment" not in leave_columns:
        op.add_column("leave_requests", sa.Column("review_comment", sa.String(1000), nullable=True))


def downgrade():
    # Forward-only: retain leave records and any historical usage/balance records.
    pass
