"""Add password reset and MFA factor tables.

Revision ID: 0009_password_reset_mfa
Revises: 0008_organization_memberships
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0009_password_reset_mfa"
down_revision = "0008_organization_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, index=True),
        sa.Column("token_hash", sa.String(length=255), nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_password_resets_email_active",
        "password_resets",
        ["organization_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND expires_at > now()"),
    )

    op.create_table(
        "mfa_factors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("factor_type", sa.String(length=20), nullable=False,
                  server_default="totp"),
        sa.Column("secret", sa.String(length=255), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False,
                  server_default="0"),
        sa.Column("backup_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  onupdate=sa.text("now()")),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("mfa_factors")
    op.drop_table("password_resets")