"""add rbac users and roles

Revision ID: 0002_rbac
Revises: 0001_initial
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_rbac"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
        """
    )
    op.execute("INSERT INTO roles (name) VALUES ('admin'), ('operator'), ('viewer')")
    op.execute(
        """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role_id INTEGER NOT NULL REFERENCES roles(id),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX idx_users_username ON users(username)")
    op.execute("CREATE INDEX idx_users_role_id ON users(role_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS roles")
