"""create show info

Revision ID: 2e81a4f63b10
Revises: cdc2dec0df8d
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2e81a4f63b10"
down_revision: Union[str, Sequence[str], None] = "cdc2dec0df8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("show_info"):
        op.create_table(
            "show_info",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("showdate", sa.Text(), nullable=False),
            sa.Column("prefucture", sa.Text(), nullable=True),
            sa.Column("showname", sa.Text(), nullable=False),
            sa.Column("venues", sa.Text(), nullable=True),
            sa.Column("starttime", sa.Text(), nullable=True),
            sa.Column("memo", sa.Text(), nullable=True),
            sa.Column("url", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("show_info")
