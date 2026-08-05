"""create schemas and extensions

Revision ID: 0001_schemas
Revises:
Create Date: 2026-08-05
"""
from alembic import op

revision = "0001_schemas"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = [
    "app_users",
    "app_mail",
    "app_monitor",
    "app_datasets",
    "app_data_registry",
    "app_ecomru",
    "app_text_dup_check",
    "app_link",
    "app_file_manager",
]


def upgrade() -> None:
    for s in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    for s in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {s} RESTRICT")