"""add account fields to users

Revision ID: a6d2c9e14b73
Revises: d51e8b0a46c2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6d2c9e14b73"
down_revision: Union[str, Sequence[str], None] = "d51e8b0a46c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
            sa.UniqueConstraint("username", name="uq_users_username"),
        )
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "userid" in columns and "id" not in columns:
        op.alter_column("users", "userid", new_column_name="id")
        columns.remove("userid")
        columns.add("id")

    if "password_hash" not in columns:
        op.add_column(
            "users",
            sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""),
        )
    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"))
    if "is_active" not in columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "created_at" not in columns:
        op.add_column("users", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    if "updated_at" not in columns:
        op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    if "usrflg" in columns:
        op.drop_column("users", "usrflg")

    constraints = {constraint["name"] for constraint in inspector.get_check_constraints("users")}
    if "ck_users_role" not in constraints:
        op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'viewer')")
    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "uq_users_username" not in unique_constraints:
        op.create_unique_constraint("uq_users_username", "users", ["username"])

    # Preserve old IDs while making future inserts receive an automatically generated ID.
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq")
    op.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 0) + 1, false)")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")
    op.execute("ALTER SEQUENCE users_id_seq OWNED BY users.id")


def downgrade() -> None:
    # The prior userid/usrflg data model cannot represent account credentials or roles.
    # Keep user data intact on downgrade.
    pass
