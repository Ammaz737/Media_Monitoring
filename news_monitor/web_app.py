"""
Web Frontend Dashboard for News Monitor
Flask-based web application for monitoring and searching news content
"""

from flask import Flask, render_template, request, jsonify, Response
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import threading
import time

from config import (
    WEB_CONFIG, ALERTS_CONFIG, RTSP_URL, RTSP_CHANNELS, DEFAULT_RTSP_CHANNELS,
    TEXT_REGIONS, YOUTUBE_TEXT_REGIONS, PROCESSING_CONFIG, SPEECH_CONFIG, UTRNET_CONFIG,
    save_runtime_config, AUTO_START_MONITORING, apply_rtsp_channels,
)
from database import NewsDatabase
from news_monitor import NewsMonitor, MultiChannelNewsMonitor

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = WEB_CONFIG['secret_key']


ALLOWED_ORIGINS = {
    'http://localhost:3000',
    'http://127.0.0.1:3000',
}


@app.after_request
def add_cors_headers(response):
    """Allow Next.js frontend to call API routes (direct or cross-origin)."""
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    elif origin:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.before_request
def handle_preflight():
    """Answer CORS preflight without a catch-all OPTIONS route (avoids HTTP 405)."""
    if request.method == 'OPTIONS' and request.path.startswith('/api/'):
        return ('', 204)


# Initialize SocketIO for real-time updates with compatibility fix
try:
    from flask_socketio import SocketIO, emit
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    SOCKETIO_ENABLED = True
except ImportError as e:
    logging.warning(f"SocketIO not available: {e}. Real-time updates will be disabled.")
    socketio = None
    SOCKETIO_ENABLED = False
    def emit(*args, **kwargs):
        pass

# Global variables
db = NewsDatabase()
news_monitor_instance = None
connected_clients = set()


def refresh_rtsp_channels_cache():
    """Seed SQLite channels if empty, then sync in-memory RTSP_CHANNELS."""
    db.seed_rtsp_channels(DEFAULT_RTSP_CHANNELS)
    apply_rtsp_channels(db.get_rtsp_channels())


refresh_rtsp_channels_cache()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/search')
def search():
    """Search page"""
    return render_template('search.html')

@app.route('/alerts')
def alerts():
    """Alerts page"""
    return render_template('alerts.html')

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

# API Routes

@app.route('/api/statistics')
def api_statistics():
    """Get system statistics"""
    try:
        # Database statistics
        db_stats = db.get_statistics()
        
        # Monitor statistics (if running)
        monitor_stats = {}
        if news_monitor_instance:
            monitor_stats = news_monitor_instance.get_statistics()
        
        stats = {
            'database': db_stats,
            'monitor': monitor_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logging.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-extractions')
def api_recent_extractions():
    """Get recent text extractions"""
    try:
        limit = request.args.get('limit', 50, type=int)
        channel = request.args.get('channel')
        region = request.args.get('region')
        
        extractions = db.search_text_extractions(
            channel_name=channel,
            region_name=region,
            limit=limit
        )
        
        return jsonify({
            'extractions': extractions,
            'count': len(extractions)
        })
        
    except Exception as e:
        logging.error(f"Error getting recent extractions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-transcriptions')
def api_recent_transcriptions():
    """Get recent audio transcriptions"""
    try:
        limit = request.args.get('limit', 20, type=int)
        channel = request.args.get('channel')
        
        transcriptions = db.search_audio_transcriptions(
            channel_name=channel,
            limit=limit
        )
        
        return jsonify({
            'transcriptions': transcriptions,
            'count': len(transcriptions)
        })
        
    except Exception as e:
        logging.error(f"Error getting recent transcriptions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-text')
def api_search_text():
    """Search text extractions"""
    try:
        query = request.args.get('q', '')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        channel = request.args.get('channel')
        region = request.args.get('region')
        min_confidence = request.args.get('min_confidence', type=float)
        limit = request.args.get('limit', WEB_CONFIG['results_per_page'], type=int)
        
        # Parse dates
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        results = db.search_text_extractions(
            query=query if query else None,
            start_date=start_datetime,
            end_date=end_datetime,
            region_name=region if region else None,
            channel_name=channel if channel else None,
            min_confidence=min_confidence,
            limit=limit
        )
        
        return jsonify({
            'results': results,
            'count': len(results),
            'query': query
        })
        
    except Exception as e:
        logging.error(f"Error searching text: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-audio')
def api_search_audio():
    """Search audio transcriptions"""
    try:
        query = request.args.get('q', '')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        channel = request.args.get('channel')
        min_confidence = request.args.get('min_confidence', type=float)
        limit = request.args.get('limit', WEB_CONFIG['results_per_page'], type=int)
        
        # Parse dates
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        results = db.search_audio_transcriptions(
            query=query if query else None,
            start_date=start_datetime,
            end_date=end_datetime,
            channel_name=channel if channel else None,
            min_confidence=min_confidence,
            limit=limit
        )
        
        return jsonify({
            'results': results,
            'count': len(results),
            'query': query
        })
        
    except Exception as e:
        logging.error(f"Error searching audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def api_alerts():
    """Get alerts"""
    try:
        is_read = request.args.get('is_read')
        alert_type = request.args.get('type')
        severity = request.args.get('severity')
        limit = request.args.get('limit', 1000, type=int)
        
        # Convert is_read parameter
        is_read_bool = None
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
        
        alerts = db.get_alerts(
            is_read=is_read_bool,
            alert_type=alert_type,
            severity=severity,
            limit=limit
        )
        counts = db.get_alert_counts()
        
        return jsonify({
            'alerts': alerts,
            'count': len(alerts),
            'totals': counts,
        })
        
    except Exception as e:
        logging.error(f"Error getting alerts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/mark-all-read', methods=['POST'])
def api_mark_all_alerts_read():
    """Mark every unread alert as read"""
    try:
        updated = db.mark_all_alerts_read()
        return jsonify({'success': True, 'updated': updated})
    except Exception as e:
        logging.error(f"Error marking all alerts read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts/<alert_uuid>/mark-read', methods=['POST'])
def api_mark_alert_read(alert_uuid):
    """Mark alert as read"""
    try:
        success = db.mark_alert_read(alert_uuid)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Alert not found'}), 404
            
    except Exception as e:
        logging.error(f"Error marking alert as read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitor/start', methods=['POST'])
def api_start_monitor():
    """Start news monitoring (multi-channel by default)."""
    try:
        global news_monitor_instance

        # Treat as running if parent flag OR any child channel is live
        if news_monitor_instance:
            already = bool(getattr(news_monitor_instance, 'is_running', False))
            if isinstance(news_monitor_instance, MultiChannelNewsMonitor):
                already = already or news_monitor_instance.any_channel_running()
            if already:
                return jsonify({'error': 'Monitor is already running'}), 400
            # Stale stopped instance — clear before restart
            try:
                news_monitor_instance.stop_monitoring()
            except Exception:
                pass
            news_monitor_instance = None

        config = request.get_json() or {}
        use_multi_channel = config.get('multi_channel', True)

        if use_multi_channel:
            refresh_rtsp_channels_cache()
            channel_configs = {
                cid: dict(cfg) for cid, cfg in RTSP_CHANNELS.items()
            }
            # Optional runtime overrides from Settings toggles
            enabled_overrides = config.get('enabled_channels')
            if isinstance(enabled_overrides, dict):
                for cid, enabled in enabled_overrides.items():
                    if cid in channel_configs:
                        channel_configs[cid]['enabled'] = bool(enabled)

            enabled_count = sum(
                1 for c in channel_configs.values() if c.get('enabled')
            )
            if enabled_count == 0:
                return jsonify({'error': 'No enabled RTSP channels'}), 400

            monitor = MultiChannelNewsMonitor(channel_configs=channel_configs)
            news_monitor_instance = monitor
            try:
                monitor.start_monitoring()
            except Exception:
                news_monitor_instance = None
                raise

            return jsonify({
                'success': True,
                'message': f'Multi-channel monitoring started ({enabled_count} channels)',
                'multi_channel': True,
                'channels': list(monitor.monitors.keys()),
                'channel_name': 'multi_channel',
            })

        # Single-channel (legacy) mode
        rtsp_url = config.get('rtsp_url') or RTSP_URL
        channel_name = config.get('channel_name', 'news_channel')

        if not rtsp_url or not str(rtsp_url).strip():
            return jsonify({'error': 'rtsp_url is required'}), 400

        monitor = NewsMonitor(rtsp_url=rtsp_url.strip(), channel_name=channel_name)
        news_monitor_instance = monitor
        try:
            monitor.start_monitoring()
        except Exception:
            news_monitor_instance = None
            raise

        return jsonify({
            'success': True,
            'message': 'News monitoring started',
            'multi_channel': False,
            'channel_name': channel_name,
            'source_url': monitor.source_url,
        })

    except Exception as e:
        logging.error(f"Error starting monitor: {e}")
        news_monitor_instance = None
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitor/stop', methods=['POST'])
def api_stop_monitor():
    """Stop news monitoring"""
    try:
        global news_monitor_instance
        
        if news_monitor_instance:
            news_monitor_instance.stop_monitoring()
            news_monitor_instance = None
        
        return jsonify({
            'success': True,
            'message': 'News monitoring stopped'
        })
        
    except Exception as e:
        logging.error(f"Error stopping monitor: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config')
def api_config():
    """Read-only configuration for settings UI."""
    try:
        refresh_rtsp_channels_cache()

        # Prefer live keywords from running monitor when available
        keywords = ALERTS_CONFIG.get('keywords', [])
        if news_monitor_instance and getattr(news_monitor_instance, 'alert_system', None):
            keywords = news_monitor_instance.alert_system.get_keywords()

        # Merge RTSP + YouTube region definitions for settings display
        text_regions = {**TEXT_REGIONS, **YOUTUBE_TEXT_REGIONS}

        return jsonify({
            'rtsp_url': RTSP_URL,
            'rtsp_channels': RTSP_CHANNELS,
            'text_regions': text_regions,
            'processing': PROCESSING_CONFIG,
            'speech': SPEECH_CONFIG,
            'utrnet': {k: v for k, v in UTRNET_CONFIG.items() if k != 'device_id'},
            'alerts': {
                'enabled': ALERTS_CONFIG.get('enabled', True),
                'keywords': keywords,
                'notification_methods': ALERTS_CONFIG.get('notification_methods', []),
            },
            'web': {
                'max_search_results': WEB_CONFIG['max_search_results'],
                'results_per_page': WEB_CONFIG['results_per_page'],
            },
            'auto_start_monitoring': AUTO_START_MONITORING,
        })
    except Exception as e:
        logging.error(f"Error getting config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/keywords', methods=['GET', 'POST'])
def api_update_keywords():
    """Add/remove/replace alert keywords and persist them."""
    try:
        if request.method == 'GET':
            keywords = ALERTS_CONFIG.get('keywords', [])
            if news_monitor_instance and getattr(news_monitor_instance, 'alert_system', None):
                keywords = news_monitor_instance.alert_system.get_keywords()
            return jsonify({'keywords': keywords})

        body = request.get_json() or {}
        action = (body.get('action') or 'set').lower()

        current = list(ALERTS_CONFIG.get('keywords', []))
        if news_monitor_instance and getattr(news_monitor_instance, 'alert_system', None):
            current = news_monitor_instance.alert_system.get_keywords()

        if action == 'add':
            to_add = body.get('keywords') or []
            if body.get('keyword'):
                to_add = list(to_add) + [body.get('keyword')]
            for kw in to_add:
                value = (kw or '').strip()
                if value and value not in current:
                    current.append(value)
        elif action == 'remove':
            to_remove = set()
            if body.get('keyword'):
                to_remove.add(str(body.get('keyword')).strip())
            for kw in body.get('keywords') or []:
                to_remove.add(str(kw).strip())
            current = [k for k in current if k not in to_remove]
        else:
            # Full replace
            incoming = body.get('keywords')
            if incoming is None:
                return jsonify({'error': 'keywords array required'}), 400
            seen = set()
            current = []
            for kw in incoming:
                value = str(kw).strip()
                if value and value not in seen:
                    current.append(value)
                    seen.add(value)

        ALERTS_CONFIG['keywords'] = current
        save_runtime_config()

        if news_monitor_instance and getattr(news_monitor_instance, 'alert_system', None):
            news_monitor_instance.alert_system.set_keywords(current)

        # Backfill alerts from recent OCR so Alerts page is not empty after save
        created = 0
        try:
            created = db.rescan_alerts_for_keywords(current, limit=300)
        except Exception as scan_err:
            logging.warning(f"Keyword rescan skipped: {scan_err}")

        return jsonify({
            'success': True,
            'keywords': current,
            'alerts_created': created,
        })
    except Exception as e:
        logging.error(f"Error updating keywords: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-facets')
def api_search_facets():
    """Distinct channels/regions for search filter dropdowns."""
    try:
        facets = db.get_search_facets()
        # Always include configured region keys as fallbacks
        known_regions = list(dict.fromkeys(
            list(facets.get('regions') or [])
            + list(TEXT_REGIONS.keys())
            + list(YOUTUBE_TEXT_REGIONS.keys())
        ))
        facets['regions'] = known_regions
        return jsonify(facets)
    except Exception as e:
        logging.error(f"Error getting search facets: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitor/status')
def api_monitor_status():
    """Get monitor status"""
    try:
        if news_monitor_instance:
            stats = news_monitor_instance.get_statistics()
            if isinstance(news_monitor_instance, MultiChannelNewsMonitor):
                running = (
                    bool(news_monitor_instance.is_running)
                    or news_monitor_instance.any_channel_running()
                )
                return jsonify({
                    'running': running,
                    'multi_channel': True,
                    'channel_name': (
                        f"{stats.get('channels_running', 0)}/"
                        f"{stats.get('channels_total', 0)} channels"
                    ),
                    'stream_error': stats.get('stream_error'),
                    'channel_status': news_monitor_instance.get_channel_status(),
                    'statistics': stats,
                })

            return jsonify({
                'running': news_monitor_instance.is_running,
                'multi_channel': False,
                'channel_name': news_monitor_instance.channel_name,
                'source_url': news_monitor_instance.source_url,
                'stream_error': news_monitor_instance.stream_error,
                'statistics': stats,
            })

        return jsonify({
            'running': False,
            'multi_channel': False,
            'channel_name': None,
            'statistics': {},
        })

    except Exception as e:
        logging.error(f"Error getting monitor status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/channels', methods=['POST'])
def api_create_channel():
    """Add a new RTSP channel (persisted in SQLite)."""
    try:
        body = request.get_json() or {}
        name = (body.get('name') or '').strip()
        rtsp_url = (body.get('rtsp_url') or '').strip()
        priority = (body.get('priority') or 'medium').strip().lower()
        enabled = bool(body.get('enabled', True))

        if not name:
            return jsonify({'error': 'name is required'}), 400
        if not rtsp_url:
            return jsonify({'error': 'rtsp_url is required'}), 400
        if priority not in ('high', 'medium', 'low'):
            priority = 'medium'

        channel_id = (body.get('channel_id') or '').strip() or db.next_rtsp_channel_id()
        if channel_id in RTSP_CHANNELS or channel_id in db.get_rtsp_channels():
            return jsonify({'error': f'Channel id already exists: {channel_id}'}), 400

        ok = db.create_rtsp_channel(
            channel_id=channel_id,
            name=name,
            rtsp_url=rtsp_url,
            enabled=enabled,
            priority=priority,
        )
        if not ok:
            return jsonify({'error': 'Failed to create channel'}), 500

        refresh_rtsp_channels_cache()
        cfg = dict(RTSP_CHANNELS[channel_id])

        if (
            news_monitor_instance
            and isinstance(news_monitor_instance, MultiChannelNewsMonitor)
            and (news_monitor_instance.is_running or news_monitor_instance.any_channel_running())
            and enabled
        ):
            news_monitor_instance.add_channel(channel_id, cfg)

        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'channel': cfg,
            'channels': RTSP_CHANNELS,
        }), 201
    except Exception as e:
        logging.error(f"Error creating channel: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/channels/<channel_id>', methods=['POST', 'PUT', 'DELETE'])
def api_update_channel(channel_id):
    """Enable/disable, update, or delete an RTSP channel."""
    try:
        if request.method == 'DELETE':
            if channel_id not in db.get_rtsp_channels():
                return jsonify({'error': 'Channel not found'}), 404
            if not db.delete_rtsp_channel(channel_id):
                return jsonify({'error': 'Failed to delete channel'}), 500
            refresh_rtsp_channels_cache()
            if (
                news_monitor_instance
                and isinstance(news_monitor_instance, MultiChannelNewsMonitor)
            ):
                news_monitor_instance.remove_channel(channel_id)
            return jsonify({
                'success': True,
                'channel_id': channel_id,
                'deleted': True,
                'channels': RTSP_CHANNELS,
            })

        body = request.get_json() or {}
        existing = db.get_rtsp_channels()
        if channel_id not in existing:
            return jsonify({'error': 'Channel not found'}), 404

        updates = {}
        if 'enabled' in body:
            updates['enabled'] = bool(body['enabled'])
        if 'name' in body and str(body['name']).strip():
            updates['name'] = str(body['name']).strip()
        if 'rtsp_url' in body and str(body['rtsp_url']).strip():
            updates['rtsp_url'] = str(body['rtsp_url']).strip()
        if 'priority' in body:
            p = str(body['priority']).strip().lower()
            if p in ('high', 'medium', 'low'):
                updates['priority'] = p

        if not updates:
            return jsonify({'error': 'No fields to update'}), 400

        if not db.update_rtsp_channel(channel_id, **updates):
            return jsonify({'error': 'Failed to update channel'}), 500

        refresh_rtsp_channels_cache()
        cfg = dict(RTSP_CHANNELS[channel_id])

        if (
            news_monitor_instance
            and isinstance(news_monitor_instance, MultiChannelNewsMonitor)
        ):
            running = (
                news_monitor_instance.is_running
                or news_monitor_instance.any_channel_running()
            )
            if 'enabled' in updates and len(updates) == 1:
                if running:
                    news_monitor_instance.set_channel_enabled(
                        channel_id, updates['enabled']
                    )
            elif running:
                # Name/URL/priority changed — restart channel if present
                news_monitor_instance.remove_channel(channel_id)
                if cfg.get('enabled'):
                    news_monitor_instance.add_channel(channel_id, cfg)

        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'enabled': cfg.get('enabled'),
            'channel': cfg,
            'channels': RTSP_CHANNELS,
        })
    except Exception as e:
        logging.error(f"Error updating channel {channel_id}: {e}")
        return jsonify({'error': str(e)}), 500

# WebSocket handlers for real-time updates
if SOCKETIO_ENABLED and socketio:
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        connected_clients.add(request.sid)
        emit('connected', {'message': 'Connected to news monitor'})
        logging.info(f"Client connected: {request.sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        connected_clients.discard(request.sid)
        logging.info(f"Client disconnected: {request.sid}")

    @socketio.on('subscribe_updates')
    def handle_subscribe_updates(data):
        """Handle subscription to real-time updates"""
        # Client wants to receive real-time updates
        emit('subscribed', {'message': 'Subscribed to real-time updates'})

# Background task for sending real-time updates
def send_real_time_updates():
    """Send real-time updates to connected clients"""
    while True:
        try:
            monitor_alive = False
            if news_monitor_instance:
                monitor_alive = bool(getattr(news_monitor_instance, 'is_running', False))
                if isinstance(news_monitor_instance, MultiChannelNewsMonitor):
                    monitor_alive = monitor_alive or news_monitor_instance.any_channel_running()

            if SOCKETIO_ENABLED and socketio and connected_clients and monitor_alive:
                # Get recent data + DB totals so dashboard counts update live
                recent_extractions = db.search_text_extractions(limit=10)
                recent_transcriptions = db.search_audio_transcriptions(limit=10)
                recent_alerts = db.get_alerts(is_read=False, limit=5)
                db_stats = db.get_statistics()
                mon_stats = news_monitor_instance.get_statistics()

                update_data = {
                    'timestamp': datetime.now().isoformat(),
                    'recent_extractions': recent_extractions,
                    'recent_transcriptions': recent_transcriptions,
                    'recent_alerts': recent_alerts,
                    'statistics': {
                        'database': db_stats,
                        'monitor': mon_stats,
                    },
                }

                # Ensure datetime fields from SQLite rows are JSON-safe
                def _json_safe(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    if isinstance(obj, dict):
                        return {k: _json_safe(v) for k, v in obj.items()}
                    if isinstance(obj, list):
                        return [_json_safe(v) for v in obj]
                    return obj

                socketio.emit('real_time_update', _json_safe(update_data))
            
            time.sleep(5)  # Send updates every 5 seconds
            
        except Exception as e:
            logging.error(f"Error in real-time updates: {e}")
            time.sleep(10)

# Start background task only if SocketIO is enabled
if SOCKETIO_ENABLED:
    update_thread = threading.Thread(target=send_real_time_updates, daemon=True)
    update_thread.start()


def _auto_start_monitoring():
    """Resume multi-channel RTSP monitoring after Flask restart."""
    global news_monitor_instance
    time.sleep(2.0)  # let the HTTP server bind first
    try:
        if news_monitor_instance and (
            news_monitor_instance.is_running
            or (
                isinstance(news_monitor_instance, MultiChannelNewsMonitor)
                and news_monitor_instance.any_channel_running()
            )
        ):
            logging.info("Auto-start skipped — monitor already running")
            return

        refresh_rtsp_channels_cache()
        if not any(cfg.get('enabled') for cfg in RTSP_CHANNELS.values()):
            logging.warning("Auto-start skipped — no enabled RTSP channels")
            return

        enabled_count = sum(1 for c in RTSP_CHANNELS.values() if c.get('enabled'))
        logging.info(
            "Auto-starting multi-channel monitoring (%s channels)…",
            enabled_count,
        )
        # Pass full channel map so Settings can enable previously-disabled channels live
        monitor = MultiChannelNewsMonitor(
            channel_configs={cid: dict(cfg) for cid, cfg in RTSP_CHANNELS.items()}
        )
        news_monitor_instance = monitor
        monitor.start_monitoring()
        logging.info("Auto-start: multi-channel monitoring launched")
    except Exception as e:
        logging.error(f"Auto-start monitoring failed: {e}")
        news_monitor_instance = None


if AUTO_START_MONITORING:
    # main.py uses use_reloader=False, so this runs once per process
    threading.Thread(
        target=_auto_start_monitoring, daemon=True, name="auto-start-monitor"
    ).start()

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the app
    if SOCKETIO_ENABLED and socketio:
        socketio.run(
            app,
            host=WEB_CONFIG['host'],
            port=WEB_CONFIG['port'],
            debug=WEB_CONFIG['debug']
        )
    else:
        logging.warning("Running without real-time updates (SocketIO disabled)")
        app.run(
            host=WEB_CONFIG['host'],
            port=WEB_CONFIG['port'],
            debug=WEB_CONFIG['debug']
        )
