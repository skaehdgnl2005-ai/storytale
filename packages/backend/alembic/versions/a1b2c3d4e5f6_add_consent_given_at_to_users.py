"""Add consent_given_at to users

Revision ID: a1b2c3d4e5f6
Revises: 76c2febda894
Create Date: 2026-04-10 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "76c2febda894"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """법정대리인(부모) 동의 일시 컬럼 추가."""
    op.add_column(
        "users",
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """consent_given_at 컬럼 제거."""
    op.drop_column("users", "consent_given_at")
