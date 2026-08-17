"""
Copy news_monitor SQLite data into Postgres.

Usage (from news_monitor/):
    python migrate_sqlite_to_postgres.py
    python migrate_sqlite_to_postgres.py --replace
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import psycopg2

from config import BASE_DIR, DATABASE_CONFIG

TABLES = (
    (
        "channels",
        (
            "id",
            "channel_name",
            "rtsp_url",
            "display_name",
            "language",
            "is_active",
            "last_seen",
            "created_at",
            "priority",
            "text_regions",
        ),
        {"is_active"},
    ),
    (
        "text_extractions",
        (
            "id",
            "uuid",
            "timestamp",
            "region_name",
            "extracted_text",
            "confidence",
            "priority",
            "region_coords",
            "frame_hash",
            "screenshot_path",
            "channel_name",
            "ocr_engine",
            "created_at",
        ),
        set(),
    ),
    (
        "audio_transcriptions",
        (
            "id",
            "uuid",
            "timestamp",
            "transcribed_text",
            "confidence",
            "duration",
            "audio_path",
            "language",
            "channel_name",
            "created_at",
        ),
        set(),
    ),
    (
        "alerts",
        (
            "id",
            "uuid",
            "timestamp",
            "alert_type",
            "content_type",
            "content_id",
            "matched_keywords",
            "alert_text",
            "severity",
            "is_read",
            "channel_name",
            "created_at",
        ),
        {"is_read"},
    ),
    (
        "daily_stats",
        (
            "id",
            "date",
            "channel_name",
            "text_extractions_count",
            "audio_transcriptions_count",
            "alerts_count",
            "processing_time_avg",
            "created_at",
        ),
        set(),
    ),
)


def _as_bool(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.lower() in ("1", "true", "t", "yes")
    return bool(value)


def _adapt(row, columns, bool_cols):
    out = []
    for col, val in zip(columns, row):
        if col in bool_cols:
            out.append(_as_bool(val))
        else:
            out.append(val)
    return tuple(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite",
        default=str(BASE_DIR / "data" / "news_monitor.db"),
        help="Path to existing SQLite database",
    )
    parser.add_argument(
        "--database-url",
        default=DATABASE_CONFIG["url"],
        help="Postgres connection URI",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate Postgres tables before copy",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        print(f"SQLite file not found: {sqlite_path}", file=sys.stderr)
        return 1

    from database import run_migrations

    run_migrations(args.database_url)

    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    dst = psycopg2.connect(args.database_url)
    dst.autocommit = False

    try:
        with dst.cursor() as cur:
            if args.replace:
                cur.execute(
                    "TRUNCATE text_extractions, audio_transcriptions, alerts, "
                    "channels, daily_stats RESTART IDENTITY"
                )
            else:
                cur.execute(
                    "SELECT "
                    "(SELECT COUNT(*) FROM text_extractions) + "
                    "(SELECT COUNT(*) FROM audio_transcriptions) + "
                    "(SELECT COUNT(*) FROM alerts) + "
                    "(SELECT COUNT(*) FROM channels) + "
                    "(SELECT COUNT(*) FROM daily_stats)"
                )
                existing = cur.fetchone()[0]
                if existing:
                    print(
                        f"Postgres already has {existing} rows. "
                        "Re-run with --replace to overwrite.",
                        file=sys.stderr,
                    )
                    return 1

            for table, columns, bool_cols in TABLES:
                present = {
                    row[1]
                    for row in src.execute(f"PRAGMA table_info({table})").fetchall()
                }
                use_cols = [c for c in columns if c in present]
                placeholders = ", ".join(["%s"] * len(use_cols))
                col_sql = ", ".join(use_cols)
                rows = src.execute(
                    f"SELECT {col_sql} FROM {table}"
                ).fetchall()
                if not rows:
                    print(f"{table}: 0 rows")
                    continue
                payload = [
                    _adapt([r[c] for c in use_cols], use_cols, bool_cols)
                    for r in rows
                ]
                cur.executemany(
                    f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
                    payload,
                )
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))",
                    (table,),
                )
                print(f"{table}: {len(payload)} rows")

        dst.commit()
    except Exception:
        dst.rollback()
        raise
    finally:
        dst.close()
        src.close()

    print("SQLite -> Postgres copy complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
