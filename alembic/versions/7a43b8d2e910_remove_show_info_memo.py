"""remove memo from show_info

Revision ID: 7a43b8d2e910
Revises: 2e81a4f63b10
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a43b8d2e910"
down_revision: Union[str, Sequence[str], None] = "2e81a4f63b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("show_info")}
    if "memo" in columns:
        with op.batch_alter_table("show_info") as batch_op:
            batch_op.drop_column("memo")


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("show_info")}
    if "memo" not in columns:
        with op.batch_alter_table("show_info") as batch_op:
            batch_op.add_column(sa.Column("memo", sa.Text(), nullable=True))
