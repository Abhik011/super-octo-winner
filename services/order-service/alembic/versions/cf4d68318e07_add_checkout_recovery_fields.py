
"""add checkout recovery fields

Revision ID: cf4d68318e07
Revises: a910918fa53e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cf4d68318e07"
down_revision: Union[str, Sequence[str], None] = "a910918fa53e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checkout_attempts",
        sa.Column("lease_token", sa.Uuid(), nullable=True),
    )

    op.add_column(
        "checkout_attempts",
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "ck_checkout_attempt_status",
        "checkout_attempts",
        type_="check",
    )

    op.create_check_constraint(
        "ck_checkout_attempt_status",
        "checkout_attempts",
        """
        status IN (
            'processing',
            'compensation_pending',
            'completed',
            'failed'
        )
        """,
    )

    op.create_index(
        "ix_checkout_attempts_lease",
        "checkout_attempts",
        ["status", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_checkout_attempts_lease",
        table_name="checkout_attempts",
    )

    op.drop_constraint(
        "ck_checkout_attempt_status",
        "checkout_attempts",
        type_="check",
    )

    op.create_check_constraint(
        "ck_checkout_attempt_status",
        "checkout_attempts",
        "status IN ('processing', 'completed', 'failed')",
    )

    op.drop_column("checkout_attempts", "lease_expires_at")
    op.drop_column("checkout_attempts", "lease_token")
