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
    WEB_CONFIG, ALERTS_CONFIG, RTSP_URL, RTSP_CHANNELS,
    TEXT_REGIONS, PROCESSING_CONFIG, SPEECH_CONFIG, UTRNET_CONFIG,
)
from database import NewsDatabase
from news_monitor import NewsMonitor

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
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route('/api/<path:_path>', methods=['OPTIONS'])
def api_options(_path):
    return '', 204

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
        limit = request.args.get('limit', 100, type=int)
        
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
        
        return jsonify({
            'alerts': alerts,
            'count': len(alerts)
        })
        
    except Exception as e:
        logging.error(f"Error getting alerts: {e}")
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
    """Start news monitoring"""
    try:
        global news_monitor_instance
        
        if news_monitor_instance and news_monitor_instance.is_running:
            return jsonify({'error': 'Monitor is already running'}), 400
        
        # Get configuration from request
        config = request.get_json() or {}
        rtsp_url = config.get('rtsp_url')
        channel_name = config.get('channel_name', 'news_channel')
        
        if not rtsp_url or not str(rtsp_url).strip():
            return jsonify({'error': 'rtsp_url is required'}), 400

        # Create and start monitor
        monitor = NewsMonitor(rtsp_url=rtsp_url.strip(), channel_name=channel_name)
        try:
            monitor.start_monitoring()
        except Exception:
            news_monitor_instance = None
            raise

        news_monitor_instance = monitor
        
        return jsonify({
            'success': True,
            'message': 'News monitoring started',
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
        return jsonify({
            'rtsp_url': RTSP_URL,
            'rtsp_channels': RTSP_CHANNELS,
            'text_regions': TEXT_REGIONS,
            'processing': PROCESSING_CONFIG,
            'speech': SPEECH_CONFIG,
            'utrnet': {k: v for k, v in UTRNET_CONFIG.items() if k != 'device_id'},
            'alerts': {
                'enabled': ALERTS_CONFIG.get('enabled', True),
                'keywords': ALERTS_CONFIG.get('keywords', []),
                'notification_methods': ALERTS_CONFIG.get('notification_methods', []),
            },
            'web': {
                'max_search_results': WEB_CONFIG['max_search_results'],
                'results_per_page': WEB_CONFIG['results_per_page'],
            },
        })
    except Exception as e:
        logging.error(f"Error getting config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitor/status')
def api_monitor_status():
    """Get monitor status"""
    try:
        if news_monitor_instance:
            stats = news_monitor_instance.get_statistics()
            return jsonify({
                'running': news_monitor_instance.is_running,
                'channel_name': news_monitor_instance.channel_name,
                'source_url': news_monitor_instance.source_url,
                'stream_error': news_monitor_instance.stream_error,
                'statistics': stats,
            })
        else:
            return jsonify({
                'running': False,
                'channel_name': None,
                'statistics': {}
            })
            
    except Exception as e:
        logging.error(f"Error getting monitor status: {e}")
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
            if SOCKETIO_ENABLED and socketio and connected_clients and news_monitor_instance and news_monitor_instance.is_running:
                # Get recent data
                recent_extractions = db.search_text_extractions(limit=5)
                recent_transcriptions = db.search_audio_transcriptions(limit=5)
                recent_alerts = db.get_alerts(is_read=False, limit=5)
                
                update_data = {
                    'timestamp': datetime.now().isoformat(),
                    'recent_extractions': recent_extractions,
                    'recent_transcriptions': recent_transcriptions,
                    'recent_alerts': recent_alerts,
                    'statistics': news_monitor_instance.get_statistics()
                }
                
                # Send to all connected clients
                socketio.emit('real_time_update', update_data)
            
            time.sleep(5)  # Send updates every 5 seconds
            
        except Exception as e:
            logging.error(f"Error in real-time updates: {e}")
            time.sleep(10)

# Start background task only if SocketIO is enabled
if SOCKETIO_ENABLED:
    update_thread = threading.Thread(target=send_real_time_updates, daemon=True)
    update_thread.start()

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
