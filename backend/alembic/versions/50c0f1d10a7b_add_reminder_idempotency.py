"""add reminder idempotency

Revision ID: 50c0f1d10a7b
Revises: 2d0aa7a8c5d1
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "50c0f1d10a7b"
down_revision: str | None = "2d0aa7a8c5d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "reminder_occurrence",
        "notifications",
        ["user_id", "meal_type", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "reminder_occurrence", "notifications", type_="unique"
    )
