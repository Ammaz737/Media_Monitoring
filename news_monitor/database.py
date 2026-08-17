"""
Database models and management for News Monitor.
PostgreSQL stores extracted text, audio transcriptions, and metadata.
"""

import json
import logging
import subprocess
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

import psycopg2
from psycopg2 import IntegrityError

from config import BASE_DIR, DATABASE_CONFIG, STORAGE_CONFIG, AUTH_CONFIG


def _cell(value):
    """JSON-safe cell: keep SQLite-like timestamp strings for the frontend."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _row_dict(columns, row) -> Dict:
    return {col: _cell(val) for col, val in zip(columns, row)}


INITIAL_REVISION = "0001_initial"
_migrations_applied = False


def run_migrations(dsn: str = None) -> None:
    """Apply Alembic migrations. Stamp existing pre-Alembic schema to 0001_initial."""
    global _migrations_applied
    if _migrations_applied:
        return

    from alembic import command
    from alembic.config import Config

    dsn = dsn or DATABASE_CONFIG["url"]
    ini = Path(__file__).parent / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", dsn.replace("%", "%%"))

    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'alembic_version'
                )
                """
            )
            has_alembic = cur.fetchone()[0]
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'text_extractions'
                )
                """
            )
            has_schema = cur.fetchone()[0]
            if has_schema and not has_alembic:
                # Match 0001_initial indexes that older CREATE TABLE skipped
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_text_timestamp_region "
                    "ON text_extractions(timestamp, region_name)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alert_severity_read "
                    "ON alerts(severity, is_read)"
                )
    finally:
        conn.close()

    if has_schema and not has_alembic:
        command.stamp(cfg, INITIAL_REVISION)
        logging.info("Stamped existing schema as %s", INITIAL_REVISION)

    command.upgrade(cfg, "head")
    _migrations_applied = True
    logging.info("Database migrations up to date")


class NewsDatabase:
    """Database manager for news monitoring system."""

    def __init__(self, dsn: str = None):
        self.dsn = dsn or DATABASE_CONFIG["url"]
        self.lock = threading.Lock()
        run_migrations(self.dsn)
        self.seed_admin_user()
        logging.info("Database initialized (%s)", self._dsn_log)

    @property
    def _dsn_log(self) -> str:
        """DSN with password stripped for logs."""
        url = self.dsn
        if "@" in url and ":" in url.split("@", 1)[0]:
            head, tail = url.rsplit("@", 1)
            scheme_user, _, _pw = head.rpartition(":")
            return f"{scheme_user}:***@{tail}"
        return url

    @contextmanager
    def _cursor(self):
        conn = psycopg2.connect(self.dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    yield cur
        finally:
            conn.close()

    def insert_text_extraction(
        self,
        region_name: str,
        text: str,
        confidence: float,
        priority: str = "medium",
        region_coords: Tuple[int, int, int, int] = None,
        frame_hash: str = None,
        screenshot_path: str = None,
        channel_name: str = "unknown",
        ocr_engine: str = "utrnet",
    ) -> str:
        record_uuid = str(uuid.uuid4())
        timestamp = datetime.now()
        engine = (ocr_engine or "utrnet").strip().lower()
        if engine not in ("utrnet", "ollama"):
            engine = "utrnet"

        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO text_extractions
                        (uuid, timestamp, region_name, extracted_text, confidence,
                         priority, region_coords, frame_hash, screenshot_path, channel_name,
                         ocr_engine)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record_uuid,
                            timestamp,
                            region_name,
                            text,
                            confidence,
                            priority,
                            json.dumps(region_coords) if region_coords else None,
                            frame_hash,
                            screenshot_path,
                            channel_name,
                            engine,
                        ),
                    )
                    return record_uuid
            except Exception as e:
                logging.error("Error inserting text extraction: %s", e)
                return None

    def insert_audio_transcription(
        self,
        text: str,
        confidence: float,
        duration: float,
        audio_path: str = None,
        language: str = "urdu",
        channel_name: str = "unknown",
        record_uuid: str = None,
        timestamp: datetime = None,
    ) -> str:
        record_uuid = record_uuid or str(uuid.uuid4())
        timestamp = timestamp or datetime.now()

        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO audio_transcriptions
                        (uuid, timestamp, transcribed_text, confidence, duration,
                         audio_path, language, channel_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record_uuid,
                            timestamp,
                            text,
                            confidence,
                            duration,
                            audio_path,
                            language,
                            channel_name,
                        ),
                    )
                    return record_uuid
            except Exception as e:
                logging.error("Error inserting audio transcription: %s", e)
                return None

    def insert_alert(
        self,
        alert_type: str,
        content_type: str,
        content_id: str,
        matched_keywords: List[str],
        alert_text: str,
        severity: str = "medium",
        channel_name: str = "unknown",
    ) -> str:
        record_uuid = str(uuid.uuid4())
        timestamp = datetime.now()

        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO alerts
                        (uuid, timestamp, alert_type, content_type, content_id,
                         matched_keywords, alert_text, severity, channel_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record_uuid,
                            timestamp,
                            alert_type,
                            content_type,
                            content_id,
                            json.dumps(matched_keywords),
                            alert_text,
                            severity,
                            channel_name or "unknown",
                        ),
                    )
                    return record_uuid
            except Exception as e:
                logging.error("Error inserting alert: %s", e)
                return None

    def search_text_extractions(
        self,
        query: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        region_name: str = None,
        channel_name: str = None,
        min_confidence: float = None,
        limit: int = 100,
    ) -> List[Dict]:
        with self._cursor() as cursor:
            sql = "SELECT * FROM text_extractions WHERE 1=1"
            params: list = []

            if query:
                sql += " AND extracted_text LIKE %s"
                params.append(f"%{query}%")
            if start_date:
                sql += " AND timestamp >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND timestamp <= %s"
                params.append(end_date)
            if region_name:
                sql += " AND region_name = %s"
                params.append(region_name)
            if channel_name:
                sql += " AND channel_name = %s"
                params.append(channel_name)
            if min_confidence:
                sql += " AND confidence >= %s"
                params.append(min_confidence)

            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                record = _row_dict(columns, row)
                if record["region_coords"]:
                    record["region_coords"] = json.loads(record["region_coords"])
                results.append(record)
            return results

    def search_audio_transcriptions(
        self,
        query: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        channel_name: str = None,
        min_confidence: float = None,
        limit: int = 100,
    ) -> List[Dict]:
        with self._cursor() as cursor:
            sql = "SELECT * FROM audio_transcriptions WHERE 1=1"
            params: list = []

            if query:
                sql += " AND transcribed_text LIKE %s"
                params.append(f"%{query}%")
            if start_date:
                sql += " AND timestamp >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND timestamp <= %s"
                params.append(end_date)
            if channel_name:
                sql += " AND channel_name = %s"
                params.append(channel_name)
            if min_confidence:
                sql += " AND confidence >= %s"
                params.append(min_confidence)

            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            return [_row_dict(columns, row) for row in cursor.fetchall()]

    def paginate_text_extractions(self, page: int = 1, per_page: int = 50) -> Dict:
        page = max(1, int(page or 1))
        per_page = min(max(1, int(per_page or 50)), 100)
        offset = (page - 1) * per_page
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM text_extractions")
            total = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT uuid, timestamp, region_name, extracted_text, confidence,
                       priority, screenshot_path, channel_name
                FROM text_extractions
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (per_page, offset),
            )
            columns = [desc[0] for desc in cursor.description]
            results = [_row_dict(columns, row) for row in cursor.fetchall()]
        total_pages = (total + per_page - 1) // per_page if per_page else 0
        return {
            "results": results,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

    def paginate_audio_transcriptions(self, page: int = 1, per_page: int = 50) -> Dict:
        page = max(1, int(page or 1))
        per_page = min(max(1, int(per_page or 50)), 100)
        offset = (page - 1) * per_page
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM audio_transcriptions")
            total = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT uuid, timestamp, transcribed_text, confidence,
                       duration, language, channel_name
                FROM audio_transcriptions
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (per_page, offset),
            )
            columns = [desc[0] for desc in cursor.description]
            results = [_row_dict(columns, row) for row in cursor.fetchall()]
        total_pages = (total + per_page - 1) // per_page if per_page else 0
        return {
            "results": results,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

    def get_alerts(
        self,
        is_read: bool = None,
        alert_type: str = None,
        severity: str = None,
        limit: int = 1000,
    ) -> List[Dict]:
        with self._cursor() as cursor:
            sql = """
                SELECT a.*,
                       te.screenshot_path,
                       at.audio_path
                FROM alerts a
                LEFT JOIN text_extractions te
                    ON a.content_id = te.uuid
                   AND a.content_type = 'text'
                LEFT JOIN audio_transcriptions at
                    ON a.content_id = at.uuid
                   AND a.content_type = 'audio'
                WHERE 1=1
            """
            params: list = []

            if is_read is not None:
                sql += " AND a.is_read = %s"
                params.append(is_read)
            if alert_type:
                sql += " AND a.alert_type = %s"
                params.append(alert_type)
            if severity:
                sql += " AND a.severity = %s"
                params.append(severity)

            sql += " ORDER BY a.timestamp DESC LIMIT %s"
            params.append(max(1, min(int(limit or 1000), 5000)))

            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                record = _row_dict(columns, row)
                if record["matched_keywords"]:
                    record["matched_keywords"] = json.loads(record["matched_keywords"])
                results.append(record)
            return results

    def get_alert_counts(self) -> Dict[str, int]:
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM alerts")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
            unread = cursor.fetchone()[0]
            return {
                "total": total,
                "unread": unread,
                "read": max(0, total - unread),
            }

    def mark_all_alerts_read(self) -> int:
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE alerts
                        SET is_read = TRUE
                        WHERE is_read = FALSE
                        """
                    )
                    return cursor.rowcount
            except Exception as e:
                logging.error("Error marking all alerts read: %s", e)
                return 0

    def mark_alert_read(self, alert_uuid: str) -> bool:
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        "UPDATE alerts SET is_read = TRUE WHERE uuid = %s",
                        (alert_uuid,),
                    )
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error("Error marking alert as read: %s", e)
                return False

    def _get_daily_activity_series(self, cursor, days: int = 14) -> List[Dict]:
        cursor.execute(
            """
            SELECT timestamp::date AS day, COUNT(*) AS cnt
            FROM text_extractions
            WHERE timestamp >= CURRENT_DATE - (%s * INTERVAL '1 day')
            GROUP BY timestamp::date
            """,
            (days,),
        )
        text_by_day = {str(row[0]): row[1] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT timestamp::date AS day, COUNT(*) AS cnt
            FROM audio_transcriptions
            WHERE timestamp >= CURRENT_DATE - (%s * INTERVAL '1 day')
            GROUP BY timestamp::date
            """,
            (days,),
        )
        audio_by_day = {str(row[0]): row[1] for row in cursor.fetchall()}

        series = []
        today = datetime.now().date()
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            series.append(
                {
                    "time": day,
                    "extractions": text_by_day.get(day, 0),
                    "transcriptions": audio_by_day.get(day, 0),
                }
            )
        return series

    def get_statistics(
        self, start_date: datetime = None, end_date: datetime = None
    ) -> Dict:
        period_start = start_date or (datetime.now() - timedelta(days=7))
        period_end = end_date or datetime.now()

        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM text_extractions")
            text_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audio_transcriptions")
            audio_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts")
            alerts_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = FALSE")
            unread_alerts = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM text_extractions
                WHERE timestamp BETWEEN %s AND %s
                """,
                (period_start, period_end),
            )
            text_count_period = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM audio_transcriptions
                WHERE timestamp BETWEEN %s AND %s
                """,
                (period_start, period_end),
            )
            audio_count_period = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM alerts
                WHERE timestamp BETWEEN %s AND %s
                """,
                (period_start, period_end),
            )
            alerts_count_period = cursor.fetchone()[0]

            recent_time = datetime.now() - timedelta(hours=24)
            cursor.execute(
                "SELECT COUNT(*) FROM text_extractions WHERE timestamp > %s",
                (recent_time,),
            )
            recent_text = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM audio_transcriptions WHERE timestamp > %s",
                (recent_time,),
            )
            recent_audio = cursor.fetchone()[0]

            chart_series = self._get_daily_activity_series(cursor)

            return {
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                },
                "totals": {
                    "text_extractions": text_count,
                    "audio_transcriptions": audio_count,
                    "alerts": alerts_count,
                    "unread_alerts": unread_alerts,
                },
                "period_totals": {
                    "text_extractions": text_count_period,
                    "audio_transcriptions": audio_count_period,
                    "alerts": alerts_count_period,
                },
                "recent_activity": {
                    "text_extractions_24h": recent_text,
                    "audio_transcriptions_24h": recent_audio,
                },
                "chart_series": chart_series,
            }

    def seed_rtsp_channels(self, defaults: Dict) -> int:
        if not defaults:
            return 0
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM channels")
                    if cursor.fetchone()[0] > 0:
                        return 0
                    inserted = 0
                    for channel_id, cfg in defaults.items():
                        cursor.execute(
                            """
                            INSERT INTO channels
                            (channel_name, rtsp_url, display_name, is_active, priority)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                channel_id,
                                cfg.get("rtsp_url") or "",
                                cfg.get("name") or channel_id,
                                bool(cfg.get("enabled", True)),
                                cfg.get("priority") or "medium",
                            ),
                        )
                        inserted += 1
                    logging.info("Seeded %s RTSP channels into database", inserted)
                    return inserted
            except Exception as e:
                logging.error("Error seeding RTSP channels: %s", e)
                return 0

    def get_rtsp_channels(self) -> Dict[str, Dict]:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT channel_name, display_name, rtsp_url, is_active, priority, text_regions
                FROM channels
                ORDER BY id ASC
                """
            )
            channels = {}
            for row in cursor.fetchall():
                cid, display_name, rtsp_url, is_active, priority, text_regions = row
                regions = None
                if text_regions:
                    try:
                        parsed = json.loads(text_regions)
                        if isinstance(parsed, dict) and parsed:
                            regions = parsed
                    except Exception:
                        regions = None
                channels[cid] = {
                    "name": display_name or cid,
                    "rtsp_url": rtsp_url or "",
                    "enabled": bool(is_active),
                    "priority": priority or "medium",
                    "text_regions": regions,
                }
            return channels

    def create_rtsp_channel(
        self,
        channel_id: str,
        name: str,
        rtsp_url: str,
        enabled: bool = True,
        priority: str = "medium",
        text_regions: Dict = None,
    ) -> bool:
        with self.lock:
            try:
                with self._cursor() as cursor:
                    regions_json = (
                        json.dumps(text_regions, ensure_ascii=False)
                        if text_regions
                        else None
                    )
                    cursor.execute(
                        """
                        INSERT INTO channels
                        (channel_name, rtsp_url, display_name, is_active, priority, text_regions)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            channel_id,
                            rtsp_url,
                            name,
                            bool(enabled),
                            priority or "medium",
                            regions_json,
                        ),
                    )
                    return True
            except IntegrityError:
                return False
            except Exception as e:
                logging.error("Error creating RTSP channel: %s", e)
                return False

    def update_rtsp_channel(
        self,
        channel_id: str,
        *,
        name: str = None,
        rtsp_url: str = None,
        enabled: bool = None,
        priority: str = None,
        text_regions: Dict = None,
        clear_text_regions: bool = False,
    ) -> bool:
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT display_name, rtsp_url, is_active, priority, text_regions
                        FROM channels WHERE channel_name = %s
                        """,
                        (channel_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    cur_name, cur_url, cur_active, cur_priority, cur_regions = row
                    new_name = name if name is not None else cur_name
                    new_url = rtsp_url if rtsp_url is not None else cur_url
                    new_active = bool(enabled) if enabled is not None else cur_active
                    new_priority = priority if priority is not None else cur_priority
                    if clear_text_regions:
                        new_regions = None
                    elif text_regions is not None:
                        new_regions = json.dumps(text_regions, ensure_ascii=False)
                    else:
                        new_regions = cur_regions
                    cursor.execute(
                        """
                        UPDATE channels
                        SET display_name = %s, rtsp_url = %s, is_active = %s, priority = %s,
                            text_regions = %s
                        WHERE channel_name = %s
                        """,
                        (
                            new_name,
                            new_url,
                            new_active,
                            new_priority or "medium",
                            new_regions,
                            channel_id,
                        ),
                    )
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error("Error updating RTSP channel %s: %s", channel_id, e)
                return False

    def delete_rtsp_channel(self, channel_id: str) -> bool:
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM channels WHERE channel_name = %s",
                        (channel_id,),
                    )
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error("Error deleting RTSP channel: %s", e)
                return False

    def next_rtsp_channel_id(self, prefix: str = "channel_") -> str:
        with self._cursor() as cursor:
            cursor.execute("SELECT channel_name FROM channels")
            existing = {row[0] for row in cursor.fetchall()}
        n = 1
        while f"{prefix}{n}" in existing:
            n += 1
        return f"{prefix}{n}"

    def get_search_facets(self) -> Dict:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT channel_name FROM text_extractions
                WHERE channel_name IS NOT NULL AND TRIM(channel_name) != ''
                ORDER BY channel_name
                """
            )
            channels = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT DISTINCT channel_name FROM audio_transcriptions
                WHERE channel_name IS NOT NULL AND TRIM(channel_name) != ''
                ORDER BY channel_name
                """
            )
            for row in cursor.fetchall():
                if row[0] not in channels:
                    channels.append(row[0])
            cursor.execute(
                """
                SELECT DISTINCT region_name FROM text_extractions
                WHERE region_name IS NOT NULL AND TRIM(region_name) != ''
                ORDER BY region_name
                """
            )
            regions = [row[0] for row in cursor.fetchall()]
            return {"channels": channels, "regions": regions}

    def rescan_alerts_for_keywords(
        self,
        keywords: List[str],
        limit: int = 200,
    ) -> int:
        if not keywords:
            return 0

        created = 0
        rows = self.search_text_extractions(limit=limit)
        for row in rows:
            text = row.get("extracted_text") or ""
            if not text:
                continue
            matched = []
            text_l = text.lower()
            for kw in keywords:
                kw_s = (kw or "").strip()
                if not kw_s:
                    continue
                if any("\u0600" <= ch <= "\u06FF" for ch in kw_s):
                    if kw_s in text:
                        matched.append(kw_s)
                elif kw_s.lower() in text_l:
                    matched.append(kw_s)
            if not matched:
                continue
            content_id = row.get("uuid")
            if not content_id:
                continue
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM alerts
                    WHERE content_id = %s AND alert_type = 'keyword_match'
                    """,
                    (content_id,),
                )
                if cursor.fetchone()[0] > 0:
                    continue
            alert_uuid = self.insert_alert(
                alert_type="keyword_match",
                content_type="text",
                content_id=content_id,
                matched_keywords=matched,
                alert_text=text[:500],
                severity="high"
                if any(kw in ["عاجل", "breaking"] for kw in matched)
                else "medium",
                channel_name=row.get("channel_name") or "unknown",
            )
            if alert_uuid:
                created += 1
        return created

    def cleanup_old_data(self, days_to_keep: int = None):
        if days_to_keep is None:
            days_to_keep = STORAGE_CONFIG["max_storage_days"]

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM text_extractions WHERE timestamp < %s",
                        (cutoff_date,),
                    )
                    deleted_text = cursor.rowcount

                    cursor.execute(
                        "DELETE FROM audio_transcriptions WHERE timestamp < %s",
                        (cutoff_date,),
                    )
                    deleted_audio = cursor.rowcount

                    alert_cutoff = datetime.now() - timedelta(days=days_to_keep * 2)
                    cursor.execute(
                        """
                        DELETE FROM alerts
                        WHERE timestamp < %s AND is_read = TRUE
                        """,
                        (alert_cutoff,),
                    )
                    deleted_alerts = cursor.rowcount

                    logging.info(
                        "Cleaned up old data: %s texts, %s audio, %s alerts",
                        deleted_text,
                        deleted_audio,
                        deleted_alerts,
                    )
            except Exception as e:
                logging.error("Error during cleanup: %s", e)

    def backup_database(self, backup_path: str = None):
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BASE_DIR / "data" / f"news_monitor_backup_{timestamp}.sql"
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["pg_dump", "--dbname", self.dsn, "-f", str(backup_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            logging.info("Database backed up to %s", backup_path)
            return backup_path
        except Exception as e:
            logging.error("Error creating backup: %s", e)
            return None

    def close(self):
        logging.info("Database connections closed")

    def seed_admin_user(self) -> None:
        """Create the default admin if the users table is empty."""
        from auth import hash_password

        username = (AUTH_CONFIG.get("admin_username") or "admin").strip().lower()
        password = AUTH_CONFIG.get("admin_password") or "admin"
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    if cursor.fetchone()[0] > 0:
                        return
                    cursor.execute("SELECT id FROM roles WHERE name = %s", ("admin",))
                    row = cursor.fetchone()
                    if not row:
                        logging.error("RBAC seed failed: admin role missing")
                        return
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, role_id, is_active)
                        VALUES (%s, %s, %s, TRUE)
                        """,
                        (username, hash_password(password), row[0]),
                    )
                if password == "admin":
                    logging.warning(
                        "Seeded admin user %r with default password — "
                        "set ADMIN_PASSWORD in .env",
                        username,
                    )
                else:
                    logging.info("Seeded admin user %r", username)
            except Exception as e:
                logging.error("Error seeding admin user: %s", e)

    def _user_row(self, row, columns) -> dict:
        record = _row_dict(columns, row)
        record["is_active"] = bool(record.get("is_active"))
        return record

    def get_user_by_username(self, username: str) -> Optional[dict]:
        username = (username or "").strip().lower()
        if not username:
            return None
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.is_active, u.created_at,
                       r.name AS role
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username = %s
                """,
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return self._user_row(row, columns)

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.is_active, u.created_at,
                       r.name AS role
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return self._user_row(row, columns)

    def list_users(self) -> list:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, u.is_active, u.created_at, r.name AS role
                FROM users u
                JOIN roles r ON r.id = u.role_id
                ORDER BY u.id
                """
            )
            columns = [desc[0] for desc in cursor.description]
            return [self._user_row(row, columns) for row in cursor.fetchall()]

    def count_admins(self, exclude_id: int = None) -> int:
        with self._cursor() as cursor:
            sql = """
                SELECT COUNT(*) FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE r.name = 'admin' AND u.is_active = TRUE
            """
            params: list = []
            if exclude_id is not None:
                sql += " AND u.id != %s"
                params.append(exclude_id)
            cursor.execute(sql, params)
            return cursor.fetchone()[0]

    def create_user(self, username: str, password: str, role: str) -> Optional[dict]:
        from auth import ROLES, hash_password

        username = (username or "").strip().lower()
        role = (role or "").strip().lower()
        if not username or role not in ROLES:
            return None
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute("SELECT id FROM roles WHERE name = %s", (role,))
                    role_row = cursor.fetchone()
                    if not role_row:
                        return None
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, role_id, is_active)
                        VALUES (%s, %s, %s, TRUE)
                        RETURNING id
                        """,
                        (username, hash_password(password), role_row[0]),
                    )
                    new_id = cursor.fetchone()[0]
                return self.get_user_by_id(new_id)
            except IntegrityError:
                return None
            except Exception as e:
                logging.error("Error creating user: %s", e)
                return None

    def update_user(
        self,
        user_id: int,
        *,
        password: str = None,
        role: str = None,
        is_active: bool = None,
    ) -> Optional[dict]:
        from auth import ROLES, hash_password

        existing = self.get_user_by_id(user_id)
        if not existing:
            return None
        new_role = (role or existing["role"]).strip().lower()
        if new_role not in ROLES:
            return None
        new_active = existing["is_active"] if is_active is None else bool(is_active)
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute("SELECT id FROM roles WHERE name = %s", (new_role,))
                    role_row = cursor.fetchone()
                    if not role_row:
                        return None
                    if password:
                        cursor.execute(
                            """
                            UPDATE users
                            SET password_hash = %s, role_id = %s, is_active = %s
                            WHERE id = %s
                            """,
                            (hash_password(password), role_row[0], new_active, user_id),
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE users SET role_id = %s, is_active = %s WHERE id = %s
                            """,
                            (role_row[0], new_active, user_id),
                        )
                return self.get_user_by_id(user_id)
            except Exception as e:
                logging.error("Error updating user %s: %s", user_id, e)
                return None

    def delete_user(self, user_id: int) -> bool:
        existing = self.get_user_by_id(user_id)
        if not existing:
            return False
        if existing["role"] == "admin" and self.count_admins(exclude_id=user_id) < 1:
            return False
        with self.lock:
            try:
                with self._cursor() as cursor:
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error("Error deleting user %s: %s", user_id, e)
                return False


def init_database() -> NewsDatabase:
    return NewsDatabase()


def create_indices():
    """Apply schema migrations (name kept for existing callers)."""
    run_migrations()
