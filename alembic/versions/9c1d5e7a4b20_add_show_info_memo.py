"""add memo to show_info

Revision ID: 9c1d5e7a4b20
Revises: 7a43b8d2e910
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c1d5e7a4b20"
down_revision: Union[str, Sequence[str], None] = "7a43b8d2e910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("show_info")}
    if "memo" not in columns:
        op.add_column("show_info", sa.Column("memo", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("show_info")}
    if "memo" in columns:
        op.drop_column("show_info", "memo")
