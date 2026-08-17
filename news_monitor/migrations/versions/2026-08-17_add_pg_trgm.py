"""add pg_trgm fuzzy search indexes

Revision ID: 0003_pg_trgm
Revises: 0002_rbac
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_pg_trgm"
down_revision: Union[str, Sequence[str], None] = "0002_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX idx_text_extracted_trgm
        ON text_extractions USING gin (extracted_text gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_audio_transcribed_trgm
        ON audio_transcriptions USING gin (transcribed_text gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audio_transcribed_trgm")
    op.execute("DROP INDEX IF EXISTS idx_text_extracted_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
