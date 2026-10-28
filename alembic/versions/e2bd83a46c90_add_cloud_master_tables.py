"""add legacy master tables needed by fresh deployments

Revision ID: e2bd83a46c90
Revises: b41d8a6e2f30
Create Date: 2026-10-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2bd83a46c90"
down_revision: Union[str, Sequence[str], None] = "b41d8a6e2f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "url_masters" in tables:
        columns = {column["name"] for column in inspector.get_columns("url_masters")}
        if "name" not in columns:
            op.add_column(
                "url_masters",
                sa.Column("name", sa.Text(), nullable=False, server_default=""),
            )

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("userid", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("username", sa.Text(), nullable=False),
            sa.Column("usrflg", sa.Integer(), nullable=False, server_default="0"),
        )

    if "user_venues" not in tables:
        op.create_table(
            "user_venues",
            sa.Column("code", sa.Integer(), nullable=False),
            sa.Column("prefucture", sa.Text(), nullable=False),
            sa.Column("venue", sa.Text(), nullable=False),
            sa.Column("userid", sa.Integer(), nullable=False),
        )

    if "prefucture_mst" not in tables:
        op.create_table(
            "prefucture_mst",
            sa.Column("code", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("prefucture", sa.Text(), nullable=False),
        )

    if "common_venues" not in tables:
        op.create_table(
            "common_venues",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("code", sa.Integer(), nullable=False),
            sa.Column("venue", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table in ("common_venues", "prefucture_mst", "user_venues", "users"):
        if table in tables:
            op.drop_table(table)
