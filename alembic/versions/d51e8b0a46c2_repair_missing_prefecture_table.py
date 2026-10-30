"""repair missing prefecture master table

Revision ID: d51e8b0a46c2
Revises: f3a91c6d8b20
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d51e8b0a46c2"
down_revision: Union[str, Sequence[str], None] = "f3a91c6d8b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("prefucture_mst"):
        op.create_table(
            "prefucture_mst",
            sa.Column("code", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("prefucture", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    # Preserve master data if this repair created the table.
    pass
