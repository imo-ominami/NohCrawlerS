"""normalize show dates to ISO format

Revision ID: b41d8a6e2f30
Revises: 9c1d5e7a4b20
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b41d8a6e2f30"
down_revision: Union[str, Sequence[str], None] = "9c1d5e7a4b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE show_info
            SET showdate = replace(showdate, '/', '-')
            WHERE showdate LIKE '%/%'
        """)
    )


def downgrade() -> None:
    pass
