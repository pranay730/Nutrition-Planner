"""add profile calculation sex

Revision ID: 2d0aa7a8c5d1
Revises: c980ff6470d2
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2d0aa7a8c5d1"
down_revision: str | None = "c980ff6470d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "calculation_sex",
            sa.Enum(
                "female",
                "male",
                name="calculationsex",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default="female",
            nullable=False,
        ),
    )
    op.alter_column("profiles", "calculation_sex", server_default=None)


def downgrade() -> None:
    op.drop_column("profiles", "calculation_sex")
