"""add failed login lockout counter

Revision ID: 8d7c1e4a9b32
Revises: f3a91c6d8b20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d7c1e4a9b32"
down_revision: Union[str, Sequence[str], None] = (
    "f3a91c6d8b20",
    "a6d2c9e14b73",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "failed_login_attempts" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("users")
    }
    if "ck_users_failed_login_attempts_nonnegative" not in constraints:
        op.create_check_constraint(
            "ck_users_failed_login_attempts_nonnegative",
            "users",
            "failed_login_attempts >= 0",
        )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_failed_login_attempts_nonnegative",
        "users",
        type_="check",
    )
    op.drop_column("users", "failed_login_attempts")
