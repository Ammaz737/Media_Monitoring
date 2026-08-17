"""initial postgres schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE text_extractions (
            id SERIAL PRIMARY KEY,
            uuid TEXT UNIQUE NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            region_name TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            priority TEXT DEFAULT 'medium',
            region_coords TEXT,
            frame_hash TEXT,
            screenshot_path TEXT,
            channel_name TEXT DEFAULT 'unknown',
            ocr_engine TEXT DEFAULT 'utrnet',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_text_timestamp ON text_extractions(timestamp)"
    )
    op.execute(
        "CREATE INDEX idx_text_region ON text_extractions(region_name)"
    )
    op.execute(
        "CREATE INDEX idx_text_priority ON text_extractions(priority)"
    )
    op.execute(
        "CREATE INDEX idx_text_timestamp_region ON text_extractions(timestamp, region_name)"
    )

    op.execute(
        """
        CREATE TABLE audio_transcriptions (
            id SERIAL PRIMARY KEY,
            uuid TEXT UNIQUE NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            transcribed_text TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            duration DOUBLE PRECISION NOT NULL,
            audio_path TEXT,
            language TEXT DEFAULT 'urdu',
            channel_name TEXT DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_audio_timestamp ON audio_transcriptions(timestamp)"
    )
    op.execute(
        "CREATE INDEX idx_audio_language ON audio_transcriptions(language)"
    )

    op.execute(
        """
        CREATE TABLE alerts (
            id SERIAL PRIMARY KEY,
            uuid TEXT UNIQUE NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            alert_type TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_id TEXT NOT NULL,
            matched_keywords TEXT NOT NULL,
            alert_text TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            is_read BOOLEAN DEFAULT FALSE,
            channel_name TEXT DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX idx_alerts_timestamp ON alerts(timestamp)")
    op.execute("CREATE INDEX idx_alerts_type ON alerts(alert_type)")
    op.execute("CREATE INDEX idx_alerts_read ON alerts(is_read)")
    op.execute("CREATE INDEX idx_alerts_channel ON alerts(channel_name)")
    op.execute(
        "CREATE INDEX idx_alert_severity_read ON alerts(severity, is_read)"
    )

    op.execute(
        """
        CREATE TABLE channels (
            id SERIAL PRIMARY KEY,
            channel_name TEXT UNIQUE NOT NULL,
            rtsp_url TEXT,
            display_name TEXT,
            language TEXT DEFAULT 'urdu',
            is_active BOOLEAN DEFAULT TRUE,
            priority TEXT DEFAULT 'medium',
            text_regions TEXT,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    op.execute(
        """
        CREATE TABLE daily_stats (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            channel_name TEXT NOT NULL,
            text_extractions_count INTEGER DEFAULT 0,
            audio_transcriptions_count INTEGER DEFAULT 0,
            alerts_count INTEGER DEFAULT 0,
            processing_time_avg DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, channel_name)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_stats")
    op.execute("DROP TABLE IF EXISTS channels")
    op.execute("DROP TABLE IF EXISTS alerts")
    op.execute("DROP TABLE IF EXISTS audio_transcriptions")
    op.execute("DROP TABLE IF EXISTS text_extractions")
