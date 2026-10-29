"""add show favorites, crawl history, and last crawl timestamp

Revision ID: f3a91c6d8b20
Revises: e2bd83a46c90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a91c6d8b20"
down_revision: Union[str, Sequence[str], None] = "e2bd83a46c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("show_info"):
        columns = {column["name"] for column in inspector.get_columns("show_info")}
        if "favorite" not in columns:
            op.add_column("show_info", sa.Column("favorite", sa.Integer(), nullable=False, server_default="0"))
        if "new" not in columns:
            op.add_column("show_info", sa.Column("new", sa.Integer(), nullable=False, server_default="0"))
    if not inspector.has_table("show_info_old"):
        op.create_table(
            "show_info_old",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("showdate", sa.Text(), nullable=False),
            sa.Column("prefucture", sa.Text()),
            sa.Column("showname", sa.Text(), nullable=False),
            sa.Column("venues", sa.Text()),
            sa.Column("starttime", sa.Text()),
            sa.Column("memo", sa.Text()),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("favorite", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("new", sa.Integer(), nullable=False, server_default="0"),
        )
    if not inspector.has_table("app_state"):
        op.create_table(
            "app_state",
            sa.Column("key", sa.Text(), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("app_state")
    op.drop_table("show_info_old")
    op.drop_column("show_info", "new")
    op.drop_column("show_info", "favorite")
