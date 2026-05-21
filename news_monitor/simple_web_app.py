"""
Simple Web App for News Monitor (No SocketIO)
Fallback version for Python 3.12 compatibility
"""

from flask import Flask, render_template_string, request, jsonify
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import threading
import time

from config import WEB_CONFIG, ALERTS_CONFIG
from database import NewsDatabase
from news_monitor import NewsMonitor

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = WEB_CONFIG['secret_key']

# Global variables
db = NewsDatabase()
news_monitor_instance = None

# Simple HTML template without real-time features
SIMPLE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Monitor Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <style>
        .urdu-text {
            font-family: 'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', serif;
            font-size: 1.1em;
            line-height: 1.8;
        }
        .card-header {
            background: linear-gradient(45deg, #007bff, #0056b3);
            color: white;
        }
        .extraction-item {
            border-left: 3px solid #007bff;
            padding: 10px;
            margin-bottom: 10px;
            background: #f8f9fa;
        }
        .stats-card:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">📺 News Monitor</a>
            <span class="navbar-text">
                <button class="btn btn-outline-light btn-sm" onclick="location.reload()">🔄 Refresh</button>
            </span>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-lg-3 col-md-6 mb-3">
                <div class="card stats-card h-100">
                    <div class="card-header">
                        <h6 class="mb-0">📄 Text Extractions</h6>
                    </div>
                    <div class="card-body text-center">
                        <h3 class="text-primary">{{ stats.totals.text_extractions }}</h3>
                        <small class="text-muted">Total extractions</small>
                        <div class="mt-2">
                            <small class="text-success">{{ stats.recent_activity.text_extractions_24h }} in last 24h</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6 mb-3">
                <div class="card stats-card h-100">
                    <div class="card-header">
                        <h6 class="mb-0">🎵 Audio Transcriptions</h6>
                    </div>
                    <div class="card-body text-center">
                        <h3 class="text-success">{{ stats.totals.audio_transcriptions }}</h3>
                        <small class="text-muted">Total transcriptions</small>
                        <div class="mt-2">
                            <small class="text-success">{{ stats.recent_activity.audio_transcriptions_24h }} in last 24h</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6 mb-3">
                <div class="card stats-card h-100">
                    <div class="card-header">
                        <h6 class="mb-0">🚨 Alerts</h6>
                    </div>
                    <div class="card-body text-center">
                        <h3 class="text-warning">{{ stats.totals.alerts }}</h3>
                        <small class="text-muted">Total alerts</small>
                        <div class="mt-2">
                            <small class="text-danger">{{ stats.totals.unread_alerts }} unread</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6 mb-3">
                <div class="card stats-card h-100">
                    <div class="card-header">
                        <h6 class="mb-0">🖥️ System Status</h6>
                    </div>
                    <div class="card-body text-center">
                        {% if monitor_running %}
                        <h3 class="text-success">فعال</h3>
                        <small class="text-muted">Running</small>
                        {% else %}
                        <h3 class="text-secondary">غیر فعال</h3>
                        <small class="text-muted">Stopped</small>
                        {% endif %}
                        <div class="mt-2 d-grid">
                            {% if monitor_running %}
                            <button class="btn btn-danger btn-sm" onclick="controlMonitor('stop')">⏹️ Stop</button>
                            {% else %}
                            <button class="btn btn-success btn-sm" onclick="controlMonitor('start')">▶️ Start</button>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Extractions -->
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Recent Text Extractions</h6>
                    </div>
                    <div class="card-body">
                        {% for item in recent_extractions %}
                        <div class="extraction-item">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge bg-primary">{{ item.region_name }}</span>
                                <small class="text-muted">{{ item.timestamp }}</small>
                            </div>
                            <div class="urdu-text">{{ item.extracted_text[:200] }}...</div>
                            <div class="mt-2">
                                <small class="text-muted">
                                    Confidence: {{ "%.1f"|format(item.confidence * 100) }}% | 
                                    Priority: {{ item.priority }} |
                                    Channel: {{ item.channel_name }}
                                </small>
                            </div>
                        </div>
                        {% else %}
                        <div class="text-center text-muted">No recent extractions</div>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- Recent Alerts -->
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Recent Alerts</h6>
                    </div>
                    <div class="card-body">
                        {% for alert in recent_alerts %}
                        <div class="alert alert-{{ alert.severity }} alert-dismissible fade show">
                            <strong>Keywords:</strong> {{ alert.matched_keywords|join(', ') }}<br>
                            <div class="urdu-text mt-1">{{ alert.alert_text[:100] }}...</div>
                            <small class="text-muted">{{ alert.timestamp }}</small>
                        </div>
                        {% else %}
                        <div class="text-center text-muted">No recent alerts</div>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Search Form -->
                <div class="card mt-3">
                    <div class="card-header">
                        <h6 class="mb-0">🔍 Search</h6>
                    </div>
                    <div class="card-body">
                        <form method="GET" action="/search">
                            <div class="mb-3">
                                <input type="text" class="form-control" name="q" placeholder="Search text..." value="{{ search_query }}">
                            </div>
                            <button type="submit" class="btn btn-primary btn-sm w-100">Search</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function controlMonitor(action) {
            fetch(`/api/monitor/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rtsp_url: 'rtsp://admin:gcs12345@192.168.2.145:554/Streaming/Channels/101',
                    channel_name: 'news_channel'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
        
        // Disable Socket.IO connection attempts
        if (typeof io !== 'undefined') {
            // Override Socket.IO if it exists
            window.io = function() { return { emit: function(){}, on: function(){} }; };
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Get statistics
        stats = db.get_statistics()
        print(f"DEBUG: Stats structure: {stats}")
        
        # Get recent data
        recent_extractions = db.search_text_extractions(limit=10)
        recent_alerts = db.get_alerts(is_read=False, limit=5)
        
        # Parse JSON fields in alerts
        for alert in recent_alerts:
            if alert.get('matched_keywords'):
                alert['matched_keywords'] = json.loads(alert['matched_keywords'])
        
        # Check monitor status
        monitor_running = news_monitor_instance and news_monitor_instance.is_running
        
        return render_template_string(
            SIMPLE_TEMPLATE,
            stats=stats,
            recent_extractions=recent_extractions,
            recent_alerts=recent_alerts,
            monitor_running=monitor_running,
            search_query=""
        )
        
    except Exception as e:
        logging.error(f"Error rendering dashboard: {e}")
        return f"Error loading dashboard: {e}", 500

@app.route('/search')
def search():
    """Search page"""
    try:
        query = request.args.get('q', '').strip()
        results = []
        
        if query:
            results = db.search_text_extractions(query=query, limit=50)
        
        # Get statistics
        stats = db.get_statistics()
        
        # Get recent alerts
        recent_alerts = db.get_alerts(is_read=False, limit=5)
        for alert in recent_alerts:
            if alert.get('matched_keywords'):
                alert['matched_keywords'] = json.loads(alert['matched_keywords'])
        
        monitor_running = news_monitor_instance and news_monitor_instance.is_running
        
        return render_template_string(
            SIMPLE_TEMPLATE,
            stats=stats,
            recent_extractions=results,
            recent_alerts=recent_alerts,
            monitor_running=monitor_running,
            search_query=query
        )
        
    except Exception as e:
        logging.error(f"Error in search: {e}")
        return f"Search error: {e}", 500

# API Routes (same as original)
@app.route('/api/statistics')
def api_statistics():
    """Get system statistics"""
    try:
        db_stats = db.get_statistics()
        monitor_stats = {}
        if news_monitor_instance:
            monitor_stats = news_monitor_instance.get_statistics()
        
        return jsonify({
            'database': db_stats,
            'monitor': monitor_stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitor/start', methods=['POST'])
def api_start_monitor():
    """Start news monitoring"""
    try:
        global news_monitor_instance
        
        if news_monitor_instance and news_monitor_instance.is_running:
            return jsonify({'error': 'Monitor is already running'}), 400
        
        config = request.get_json() or {}
        rtsp_url = config.get('rtsp_url', 'rtsp://admin:gcs12345@192.168.2.145:554/Streaming/Channels/101')
        channel_name = config.get('channel_name', 'news_channel')
        
        news_monitor_instance = NewsMonitor(rtsp_url=rtsp_url, channel_name=channel_name)
        news_monitor_instance.start_monitoring()
        
        return jsonify({
            'success': True,
            'message': 'News monitoring started',
            'channel_name': channel_name
        })
        
    except Exception as e:
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
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Starting Simple News Monitor Web Interface")
    print("Note: Real-time updates are disabled in this version")
    print(f"Open: http://{WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
    
    app.run(
        host=WEB_CONFIG['host'],
        port=WEB_CONFIG['port'],
        debug=WEB_CONFIG['debug']
    )