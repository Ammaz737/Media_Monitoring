"""
Database Models and Management for News Monitor
Stores extracted text, audio transcriptions, and metadata
"""

import sqlite3
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import uuid

from config import DATABASE_CONFIG, STORAGE_CONFIG

class NewsDatabase:
    """
    Database manager for news monitoring system
    Handles text extractions, transcriptions, and metadata
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_CONFIG['path']
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        
        self._create_tables()
        logging.info(f"Database initialized at {self.db_path}")
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Text extractions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS text_extractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    timestamp DATETIME NOT NULL,
                    region_name TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    region_coords TEXT,
                    frame_hash TEXT,
                    screenshot_path TEXT,
                    channel_name TEXT DEFAULT 'unknown',
                    ocr_engine TEXT DEFAULT 'utrnet',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices for text extractions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_timestamp ON text_extractions(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_region ON text_extractions(region_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_priority ON text_extractions(priority)")
            
            # Audio transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audio_transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    timestamp DATETIME NOT NULL,
                    transcribed_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    duration REAL NOT NULL,
                    audio_path TEXT,
                    language TEXT DEFAULT 'urdu',
                    channel_name TEXT DEFAULT 'unknown',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices for audio transcriptions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_timestamp ON audio_transcriptions(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_language ON audio_transcriptions(language)")
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    timestamp DATETIME NOT NULL,
                    alert_type TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    matched_keywords TEXT NOT NULL,
                    alert_text TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    is_read BOOLEAN DEFAULT FALSE,
                    channel_name TEXT DEFAULT 'unknown',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrate older DBs that lack channel_name on alerts
            cursor.execute("PRAGMA table_info(alerts)")
            alert_cols = {row[1] for row in cursor.fetchall()}
            if "channel_name" not in alert_cols:
                cursor.execute(
                    "ALTER TABLE alerts ADD COLUMN channel_name TEXT DEFAULT 'unknown'"
                )
                # Backfill from linked text / audio rows when possible
                cursor.execute(
                    """
                    UPDATE alerts
                    SET channel_name = (
                        SELECT te.channel_name FROM text_extractions te
                        WHERE te.uuid = alerts.content_id
                    )
                    WHERE content_type = 'text'
                      AND (channel_name IS NULL OR channel_name = '' OR channel_name = 'unknown')
                      AND EXISTS (
                          SELECT 1 FROM text_extractions te
                          WHERE te.uuid = alerts.content_id AND te.channel_name IS NOT NULL
                      )
                    """
                )
                cursor.execute(
                    """
                    UPDATE alerts
                    SET channel_name = (
                        SELECT at.channel_name FROM audio_transcriptions at
                        WHERE at.uuid = alerts.content_id
                    )
                    WHERE content_type = 'audio'
                      AND (channel_name IS NULL OR channel_name = '' OR channel_name = 'unknown')
                      AND EXISTS (
                          SELECT 1 FROM audio_transcriptions at
                          WHERE at.uuid = alerts.content_id AND at.channel_name IS NOT NULL
                      )
                    """
                )
            
            # OCR engine tag (utrnet | ollama) for dashboard badges
            cursor.execute("PRAGMA table_info(text_extractions)")
            text_cols = {row[1] for row in cursor.fetchall()}
            if "ocr_engine" not in text_cols:
                cursor.execute(
                    "ALTER TABLE text_extractions ADD COLUMN ocr_engine TEXT DEFAULT 'utrnet'"
                )

            # Create indices for alerts
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_read ON alerts(is_read)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_channel ON alerts(channel_name)"
            )
            
            # Channel metadata table (source of truth for RTSP stream configs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT UNIQUE NOT NULL,
                    rtsp_url TEXT,
                    display_name TEXT,
                    language TEXT DEFAULT 'urdu',
                    is_active BOOLEAN DEFAULT TRUE,
                    priority TEXT DEFAULT 'medium',
                    last_seen DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migrate older DBs that lack priority / text_regions
            cursor.execute("PRAGMA table_info(channels)")
            channel_cols = {row[1] for row in cursor.fetchall()}
            if 'priority' not in channel_cols:
                cursor.execute(
                    "ALTER TABLE channels ADD COLUMN priority TEXT DEFAULT 'medium'"
                )
            if 'text_regions' not in channel_cols:
                cursor.execute(
                    "ALTER TABLE channels ADD COLUMN text_regions TEXT"
                )

            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    channel_name TEXT NOT NULL,
                    text_extractions_count INTEGER DEFAULT 0,
                    audio_transcriptions_count INTEGER DEFAULT 0,
                    alerts_count INTEGER DEFAULT 0,
                    processing_time_avg REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, channel_name)
                )
            """)
            
            conn.commit()
    
    def insert_text_extraction(self, 
                             region_name: str,
                             text: str,
                             confidence: float,
                             priority: str = 'medium',
                             region_coords: Tuple[int, int, int, int] = None,
                             frame_hash: str = None,
                             screenshot_path: str = None,
                             channel_name: str = 'unknown',
                             ocr_engine: str = 'utrnet') -> str:
        """
        Insert a text extraction record
        
        Returns:
            UUID of the inserted record
        """
        record_uuid = str(uuid.uuid4())
        timestamp = datetime.now()
        engine = (ocr_engine or 'utrnet').strip().lower()
        if engine not in ('utrnet', 'ollama'):
            engine = 'utrnet'
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO text_extractions 
                        (uuid, timestamp, region_name, extracted_text, confidence, 
                         priority, region_coords, frame_hash, screenshot_path, channel_name,
                         ocr_engine)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_uuid, timestamp, region_name, text, confidence,
                        priority, json.dumps(region_coords) if region_coords else None,
                        frame_hash, screenshot_path, channel_name, engine
                    ))
                    
                    conn.commit()
                    return record_uuid
                    
            except Exception as e:
                logging.error(f"Error inserting text extraction: {e}")
                return None
    
    def insert_audio_transcription(self,
                                 text: str,
                                 confidence: float,
                                 duration: float,
                                 audio_path: str = None,
                                 language: str = 'urdu',
                                 channel_name: str = 'unknown',
                                 record_uuid: str = None,
                                 timestamp: datetime = None) -> str:
        """
        Insert an audio transcription record
        
        Returns:
            UUID of the inserted record
        """
        record_uuid = record_uuid or str(uuid.uuid4())
        timestamp = timestamp or datetime.now()
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO audio_transcriptions 
                        (uuid, timestamp, transcribed_text, confidence, duration,
                         audio_path, language, channel_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_uuid, timestamp, text, confidence, duration,
                        audio_path, language, channel_name
                    ))
                    
                    conn.commit()
                    return record_uuid
                    
            except Exception as e:
                logging.error(f"Error inserting audio transcription: {e}")
                return None
    
    def insert_alert(self,
                     alert_type: str,
                     content_type: str,
                     content_id: str,
                     matched_keywords: List[str],
                     alert_text: str,
                     severity: str = 'medium',
                     channel_name: str = 'unknown') -> str:
        """
        Insert an alert record
        
        Returns:
            UUID of the inserted record
        """
        record_uuid = str(uuid.uuid4())
        timestamp = datetime.now()
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO alerts 
                        (uuid, timestamp, alert_type, content_type, content_id,
                         matched_keywords, alert_text, severity, channel_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_uuid, timestamp, alert_type, content_type, content_id,
                        json.dumps(matched_keywords), alert_text, severity,
                        channel_name or 'unknown',
                    ))
                    
                    conn.commit()
                    return record_uuid
                    
            except Exception as e:
                logging.error(f"Error inserting alert: {e}")
                return None
    
    def search_text_extractions(self,
                              query: str = None,
                              start_date: datetime = None,
                              end_date: datetime = None,
                              region_name: str = None,
                              channel_name: str = None,
                              min_confidence: float = None,
                              limit: int = 100) -> List[Dict]:
        """Search text extractions with filters"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM text_extractions WHERE 1=1"
            params = []
            
            if query:
                sql += " AND extracted_text LIKE ?"
                params.append(f"%{query}%")
            
            if start_date:
                sql += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                sql += " AND timestamp <= ?"
                params.append(end_date)
            
            if region_name:
                sql += " AND region_name = ?"
                params.append(region_name)
            
            if channel_name:
                sql += " AND channel_name = ?"
                params.append(channel_name)
            
            if min_confidence:
                sql += " AND confidence >= ?"
                params.append(min_confidence)
            
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                # Parse JSON fields
                if record['region_coords']:
                    record['region_coords'] = json.loads(record['region_coords'])
                results.append(record)
            
            return results
    
    def search_audio_transcriptions(self,
                                  query: str = None,
                                  start_date: datetime = None,
                                  end_date: datetime = None,
                                  channel_name: str = None,
                                  min_confidence: float = None,
                                  limit: int = 100) -> List[Dict]:
        """Search audio transcriptions with filters"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM audio_transcriptions WHERE 1=1"
            params = []
            
            if query:
                sql += " AND transcribed_text LIKE ?"
                params.append(f"%{query}%")
            
            if start_date:
                sql += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                sql += " AND timestamp <= ?"
                params.append(end_date)
            
            if channel_name:
                sql += " AND channel_name = ?"
                params.append(channel_name)
            
            if min_confidence:
                sql += " AND confidence >= ?"
                params.append(min_confidence)
            
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return results
    
    def get_alerts(self,
                   is_read: bool = None,
                   alert_type: str = None,
                   severity: str = None,
                   limit: int = 1000) -> List[Dict]:
        """Get alerts with filters"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
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
            params = []
            
            if is_read is not None:
                sql += " AND a.is_read = ?"
                params.append(is_read)
            
            if alert_type:
                sql += " AND a.alert_type = ?"
                params.append(alert_type)
            
            if severity:
                sql += " AND a.severity = ?"
                params.append(severity)
            
            sql += " ORDER BY a.timestamp DESC LIMIT ?"
            params.append(max(1, min(int(limit or 1000), 5000)))
            
            cursor.execute(sql, params)
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                # Parse JSON fields
                if record['matched_keywords']:
                    record['matched_keywords'] = json.loads(record['matched_keywords'])
                results.append(record)
            
            return results

    def get_alert_counts(self) -> Dict[str, int]:
        """Total / unread / read alert counts (not limited by page size)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alerts")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0 OR is_read = FALSE")
            unread = cursor.fetchone()[0]
            return {
                'total': total,
                'unread': unread,
                'read': max(0, total - unread),
            }

    def mark_all_alerts_read(self) -> int:
        """Mark every unread alert as read. Returns rows updated."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE alerts
                        SET is_read = TRUE
                        WHERE is_read = 0 OR is_read = FALSE
                        """
                    )
                    conn.commit()
                    return cursor.rowcount
            except Exception as e:
                logging.error(f"Error marking all alerts read: {e}")
                return 0
    
    def mark_alert_read(self, alert_uuid: str) -> bool:
        """Mark an alert as read"""
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE alerts SET is_read = TRUE 
                        WHERE uuid = ?
                    """, (alert_uuid,))
                    
                    conn.commit()
                    return cursor.rowcount > 0
                    
            except Exception as e:
                logging.error(f"Error marking alert as read: {e}")
                return False
    
    def _get_daily_activity_series(self, cursor, days: int = 14) -> List[Dict]:
        """Daily extraction/transcription counts for chart (fills last N days)."""
        cursor.execute(
            """
            SELECT date(timestamp) AS day, COUNT(*) AS cnt
            FROM text_extractions
            WHERE timestamp >= date('now', ?)
            GROUP BY date(timestamp)
            """,
            (f'-{days} day',),
        )
        text_by_day = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT date(timestamp) AS day, COUNT(*) AS cnt
            FROM audio_transcriptions
            WHERE timestamp >= date('now', ?)
            GROUP BY date(timestamp)
            """,
            (f'-{days} day',),
        )
        audio_by_day = {row[0]: row[1] for row in cursor.fetchall()}

        series = []
        today = datetime.now().date()
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            series.append({
                'time': day,
                'extractions': text_by_day.get(day, 0),
                'transcriptions': audio_by_day.get(day, 0),
            })
        return series

    def get_statistics(self, 
                      start_date: datetime = None, 
                      end_date: datetime = None) -> Dict:
        """Get system statistics"""
        
        period_start = start_date or (datetime.now() - timedelta(days=7))
        period_end = end_date or datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # All-time totals (used by dashboard stat cards)
            cursor.execute("SELECT COUNT(*) FROM text_extractions")
            text_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM audio_transcriptions")
            audio_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM alerts")
            alerts_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM alerts 
                WHERE is_read = FALSE
            """)
            unread_alerts = cursor.fetchone()[0]
            
            # Period-filtered counts (optional / analytics)
            cursor.execute("""
                SELECT COUNT(*) FROM text_extractions 
                WHERE timestamp BETWEEN ? AND ?
            """, (period_start, period_end))
            text_count_period = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM audio_transcriptions 
                WHERE timestamp BETWEEN ? AND ?
            """, (period_start, period_end))
            audio_count_period = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM alerts 
                WHERE timestamp BETWEEN ? AND ?
            """, (period_start, period_end))
            alerts_count_period = cursor.fetchone()[0]
            
            # Recent activity (last 24 hours)
            recent_time = datetime.now() - timedelta(hours=24)
            cursor.execute("""
                SELECT COUNT(*) FROM text_extractions 
                WHERE timestamp > ?
            """, (recent_time,))
            recent_text = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM audio_transcriptions 
                WHERE timestamp > ?
            """, (recent_time,))
            recent_audio = cursor.fetchone()[0]

            chart_series = self._get_daily_activity_series(cursor)
            
            return {
                'period': {
                    'start': period_start.isoformat(),
                    'end': period_end.isoformat()
                },
                'totals': {
                    'text_extractions': text_count,
                    'audio_transcriptions': audio_count,
                    'alerts': alerts_count,
                    'unread_alerts': unread_alerts
                },
                'period_totals': {
                    'text_extractions': text_count_period,
                    'audio_transcriptions': audio_count_period,
                    'alerts': alerts_count_period,
                },
                'recent_activity': {
                    'text_extractions_24h': recent_text,
                    'audio_transcriptions_24h': recent_audio
                },
                'chart_series': chart_series,
            }

    def seed_rtsp_channels(self, defaults: Dict) -> int:
        """Insert default RTSP channels when the table is empty. Returns rows inserted."""
        if not defaults:
            return 0
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM channels")
                    if cursor.fetchone()[0] > 0:
                        return 0
                    inserted = 0
                    for channel_id, cfg in defaults.items():
                        cursor.execute(
                            """
                            INSERT INTO channels
                            (channel_name, rtsp_url, display_name, is_active, priority)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                channel_id,
                                cfg.get('rtsp_url') or '',
                                cfg.get('name') or channel_id,
                                1 if cfg.get('enabled', True) else 0,
                                cfg.get('priority') or 'medium',
                            ),
                        )
                        inserted += 1
                    conn.commit()
                    logging.info("Seeded %s RTSP channels into database", inserted)
                    return inserted
            except Exception as e:
                logging.error(f"Error seeding RTSP channels: {e}")
                return 0

    def get_rtsp_channels(self) -> Dict[str, Dict]:
        """Load RTSP channel configs keyed by channel_name (id)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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
                    'name': display_name or cid,
                    'rtsp_url': rtsp_url or '',
                    'enabled': bool(is_active),
                    'priority': priority or 'medium',
                    'text_regions': regions,
                }
            return channels

    def create_rtsp_channel(
        self,
        channel_id: str,
        name: str,
        rtsp_url: str,
        enabled: bool = True,
        priority: str = 'medium',
        text_regions: Dict = None,
    ) -> bool:
        """Insert a new RTSP channel. Returns False if id already exists."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    regions_json = (
                        json.dumps(text_regions, ensure_ascii=False)
                        if text_regions
                        else None
                    )
                    cursor.execute(
                        """
                        INSERT INTO channels
                        (channel_name, rtsp_url, display_name, is_active, priority, text_regions)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            channel_id,
                            rtsp_url,
                            name,
                            1 if enabled else 0,
                            priority or 'medium',
                            regions_json,
                        ),
                    )
                    conn.commit()
                    return True
            except sqlite3.IntegrityError:
                return False
            except Exception as e:
                logging.error(f"Error creating RTSP channel: {e}")
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
        """Update fields on an existing RTSP channel."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT display_name, rtsp_url, is_active, priority, text_regions
                        FROM channels WHERE channel_name = ?
                        """,
                        (channel_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    cur_name, cur_url, cur_active, cur_priority, cur_regions = row
                    new_name = name if name is not None else cur_name
                    new_url = rtsp_url if rtsp_url is not None else cur_url
                    new_active = (1 if enabled else 0) if enabled is not None else cur_active
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
                        SET display_name = ?, rtsp_url = ?, is_active = ?, priority = ?,
                            text_regions = ?
                        WHERE channel_name = ?
                        """,
                        (
                            new_name,
                            new_url,
                            new_active,
                            new_priority or 'medium',
                            new_regions,
                            channel_id,
                        ),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error(f"Error updating RTSP channel {channel_id}: {e}")
                return False

    def delete_rtsp_channel(self, channel_id: str) -> bool:
        """Delete an RTSP channel by id."""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM channels WHERE channel_name = ?",
                        (channel_id,),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error(f"Error deleting RTSP channel {channel_id}: {e}")
                return False

    def next_rtsp_channel_id(self, prefix: str = 'channel_') -> str:
        """Allocate next unused channel_N id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name FROM channels")
            existing = {row[0] for row in cursor.fetchall()}
        n = 1
        while f"{prefix}{n}" in existing:
            n += 1
        return f"{prefix}{n}"

    def get_search_facets(self) -> Dict:
        """Distinct channel/region values for search filters."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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
            return {'channels': channels, 'regions': regions}

    def rescan_alerts_for_keywords(
        self,
        keywords: List[str],
        limit: int = 200,
    ) -> int:
        """Create alerts for recent text that matches current keywords."""
        if not keywords:
            return 0

        created = 0
        rows = self.search_text_extractions(limit=limit)
        for row in rows:
            text = row.get('extracted_text') or ''
            if not text:
                continue
            matched = []
            text_l = text.lower()
            for kw in keywords:
                kw_s = (kw or '').strip()
                if not kw_s:
                    continue
                # Arabic/Urdu: case-folding is a no-op; English: lower both
                if any('\u0600' <= ch <= '\u06FF' for ch in kw_s):
                    if kw_s in text:
                        matched.append(kw_s)
                elif kw_s.lower() in text_l:
                    matched.append(kw_s)
            if not matched:
                continue
            # Avoid duplicate alerts for same content + same keyword set
            content_id = row.get('uuid')
            if not content_id:
                continue
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM alerts
                    WHERE content_id = ? AND alert_type = 'keyword_match'
                    """,
                    (content_id,),
                )
                if cursor.fetchone()[0] > 0:
                    continue
            alert_uuid = self.insert_alert(
                alert_type='keyword_match',
                content_type='text',
                content_id=content_id,
                matched_keywords=matched,
                alert_text=text[:500],
                severity='high' if any(kw in ['عاجل', 'breaking'] for kw in matched) else 'medium',
                channel_name=row.get('channel_name') or 'unknown',
            )
            if alert_uuid:
                created += 1
        return created
    
    def cleanup_old_data(self, days_to_keep: int = None):
        """Clean up old data based on retention policy"""
        
        if days_to_keep is None:
            days_to_keep = STORAGE_CONFIG['max_storage_days']
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Clean up text extractions
                    cursor.execute("""
                        DELETE FROM text_extractions 
                        WHERE timestamp < ?
                    """, (cutoff_date,))
                    deleted_text = cursor.rowcount
                    
                    # Clean up audio transcriptions
                    cursor.execute("""
                        DELETE FROM audio_transcriptions 
                        WHERE timestamp < ?
                    """, (cutoff_date,))
                    deleted_audio = cursor.rowcount
                    
                    # Clean up old alerts (keep for longer)
                    alert_cutoff = datetime.now() - timedelta(days=days_to_keep * 2)
                    cursor.execute("""
                        DELETE FROM alerts 
                        WHERE timestamp < ? AND is_read = TRUE
                    """, (alert_cutoff,))
                    deleted_alerts = cursor.rowcount
                    
                    conn.commit()
                    
                    logging.info(f"Cleaned up old data: {deleted_text} texts, "
                               f"{deleted_audio} audio, {deleted_alerts} alerts")
                    
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")
    
    def backup_database(self, backup_path: str = None):
        """Create a backup of the database"""
        
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.parent / f"news_monitor_backup_{timestamp}.db"
        
        try:
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup:
                    source.backup(backup)
            
            logging.info(f"Database backed up to {backup_path}")
            return backup_path
            
        except Exception as e:
            logging.error(f"Error creating backup: {e}")
            return None
    
    def close(self):
        """Close database connections"""
        # SQLite connections are automatically closed when going out of scope
        logging.info("Database connections closed")


# Utility functions
def init_database() -> NewsDatabase:
    """Initialize and return database instance"""
    return NewsDatabase()

def create_indices():
    """Create additional indices for better performance"""
    db = NewsDatabase()
    
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        
        # Additional indices for better search performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_content ON text_extractions(extracted_text)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_content ON audio_transcriptions(transcribed_text)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_timestamp_region ON text_extractions(timestamp, region_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_severity_read ON alerts(severity, is_read)")
        
        conn.commit()
    
    logging.info("Additional database indices created")