"""
Modern Professional Web Dashboard for News Monitor
TVeyes-like interface with clean design
"""

from flask import Flask, render_template_string, request, jsonify, send_from_directory
import json
import logging
from datetime import datetime, timedelta
import datetime as dt
from typing import Dict, List
import threading
import time

# Try to import Chart.js for analytics (optional)
try:
    # Chart.js will be loaded from CDN in the template
    CHART_JS_AVAILABLE = True
except ImportError:
    CHART_JS_AVAILABLE = False

from config import WEB_CONFIG, ALERTS_CONFIG
from database import NewsDatabase
from news_monitor import NewsMonitor, MultiChannelNewsMonitor

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = WEB_CONFIG['secret_key']

# Global variables
db = NewsDatabase()
news_monitor_instance = None  # Can be either NewsMonitor or MultiChannelNewsMonitor

# Professional template matching the requested design
MODERN_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>📺 News Monitor Dashboard</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        :root {
            --primary-color: #4F46E5;
            --secondary-color: #7C3AED;
            --success-color: #059669;
            --warning-color: #D97706;
            --danger-color: #DC2626;
            --dark-color: #1F2937;
            --light-bg: #F9FAFB;
            --card-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            padding: 1rem 0;
        }
        
        .header h1 {
            color: var(--dark-color);
            font-weight: 700;
            margin: 0;
            font-size: 1.5rem;
        }
        
        .header .subtitle {
            color: #6B7280;
            font-size: 0.875rem;
            margin: 0;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #DC2626;
        }
        
        .status-dot.connected {
            background: var(--success-color);
        }
        
        .main-container {
            padding: 2rem 0;
        }
        
        .sidebar {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: var(--card-shadow);
            height: fit-content;
            margin-bottom: 2rem;
        }
        
        .content-area {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: var(--card-shadow);
            min-height: 600px;
        }
        
        .activity-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0;
            color: var(--primary-color);
        }
        
        .stat-number.transcriptions {
            color: var(--secondary-color);
        }
        
        .stat-label {
            color: #6B7280;
            font-size: 0.875rem;
            margin: 0;
        }
        
        .stat-hours {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--warning-color);
            margin: 1rem 0 0 0;
        }
        
        .search-section, .filters-section {
            margin-bottom: 2rem;
        }
        
        .search-section h3, .filters-section h3 {
            font-size: 1rem;
            font-weight: 600;
            color: var(--dark-color);
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .form-control {
            border: 1px solid #D1D5DB;
            border-radius: 8px;
            padding: 0.75rem;
            font-size: 0.875rem;
        }
        
        .form-control:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        
        .btn-primary {
            background: var(--primary-color);
            border: none;
            border-radius: 8px;
            font-weight: 500;
            padding: 0.75rem 1.5rem;
        }
        
        .btn-primary:hover {
            background: #3730A3;
        }
        
        .nav-tabs {
            border: none;
            margin-bottom: 1.5rem;
        }
        
        .nav-tabs .nav-link {
            border: none;
            border-radius: 8px;
            margin-right: 0.5rem;
            color: #6B7280;
            font-weight: 500;
            padding: 0.75rem 1.5rem;
            background: #F3F4F6;
        }
        
        .nav-tabs .nav-link.active {
            background: var(--primary-color);
            color: white;
        }
        
        .activity-feed {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .activity-item {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            background: #F9FAFB;
            border-left: 4px solid var(--primary-color);
        }
        
        .activity-item.transcription {
            border-left-color: var(--secondary-color);
        }
        
        .activity-badge {
            flex-shrink: 0;
            background: var(--primary-color);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            height: fit-content;
        }
        
        .activity-badge.transcription {
            background: var(--secondary-color);
        }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-text {
            font-family: 'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', serif;
            font-size: 1rem;
            line-height: 1.6;
            color: var(--dark-color);
            margin-bottom: 0.5rem;
            text-align: right;
            direction: rtl;
        }
        
        .activity-meta {
            font-size: 0.75rem;
            color: #6B7280;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .trending-keywords {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        
        .keyword-tag {
            background: #E5E7EB;
            color: var(--dark-color);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            text-decoration: none;
        }
        
        .keyword-tag:hover {
            background: var(--primary-color);
            color: white;
            text-decoration: none;
        }
        
        .quick-filters .btn {
            border-radius: 20px;
            font-size: 0.75rem;
            padding: 0.5rem 1rem;
            margin-bottom: 0.5rem;
            display: block;
            width: 100%;
            text-align: left;
            border: 1px solid #D1D5DB;
            background: white;
            color: var(--dark-color);
        }
        
        .quick-filters .btn.active {
            background: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        
        .timeline {
            position: relative;
            padding-left: 2rem;
        }
        
        .timeline::before {
            content: '';
            position: absolute;
            left: 1rem;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(to bottom, var(--primary-color), var(--secondary-color));
        }
        
        .timeline-item {
            position: relative;
            margin-bottom: 0;
        }
        
        .timeline-item::before {
            content: '';
            position: absolute;
            left: -2.25rem;
            top: 1rem;
            width: 8px;
            height: 8px;
            background: var(--primary-color);
            border-radius: 50%;
        }
        
        .monitor-controls {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            z-index: 1000;
        }
        
        .btn-monitor {
            border-radius: 50px;
            padding: 1rem 2rem;
            font-weight: 600;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            border: none;
        }
        
        .btn-start {
            background: linear-gradient(135deg, var(--success-color), #10B981);
            color: white;
        }
        
        .btn-stop {
            background: linear-gradient(135deg, var(--danger-color), #EF4444);
            color: white;
        }
        
        .auto-refresh {
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 1001;
        }
        
        .refresh-indicator {
            background: rgba(255, 255, 255, 0.9);
            border-radius: 20px;
            padding: 0.5rem 1rem;
            font-size: 0.75rem;
            color: var(--dark-color);
            border: 1px solid rgba(0, 0, 0, 0.1);
        }
        
        .btn-sm {
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            border-radius: 6px;
        }
        
        .modal-xl {
            max-width: 90%;
        }
        
        .channel-item {
            border-left: 3px solid var(--success-color);
        }

        .channel-item:not(.running) {
            border-left-color: var(--danger-color);
        }

        .channel-stats span {
            margin-right: 0.5rem;
        }

        .channel-stats span:not(:last-child)::after {
            content: " • ";
            margin-left: 0.5rem;
            color: #9CA3AF;
        }

        @media (max-width: 768px) {
            .activity-stats {
                grid-template-columns: 1fr;
                gap: 1rem;
            }

            .main-container {
                padding: 1rem 0;
            }
        }
    </style>
</head>
<body>
    <!-- Auto Refresh Indicator -->
    <div class="auto-refresh">
        <div class="refresh-indicator">
            <div class="status-indicator">
                <div class="status-dot {{ 'connected' if monitor_running else '' }}"></div>
                <span>{{ 'Connected' if monitor_running else 'Disconnected' }}</span>
                <i class="fas fa-sync-alt ms-2"></i>
                <span>Auto Refresh ON</span>
            </div>
        </div>
    </div>

    <!-- Header -->
    <div class="header">
        <div class="container-fluid">
            <div class="row align-items-center">
                <div class="col">
                    <h1><i class="fas fa-tv me-2"></i>News Monitor Dashboard</h1>
                    <p class="subtitle">Real-time Urdu News Channel Monitoring System</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-container">
        <div class="container-fluid">
            <div class="row">
                <!-- Sidebar -->
                <div class="col-lg-3">
                    <div class="sidebar">
                        <!-- Activity Stats -->
                        <div class="activity-stats">
                            <div class="stat-item">
                                <p class="stat-number">{{ stats.totals.text_extractions }}</p>
                                <p class="stat-label">OCR Captures</p>
                            </div>
                            <div class="stat-item">
                                <p class="stat-number transcriptions">{{ stats.totals.audio_transcriptions }}</p>
                                <p class="stat-label">Transcriptions</p>
                            </div>
                        </div>
                        <div class="text-center">
                            <p class="stat-hours">{{ "%.1f"|format(stats.totals.text_extractions * 0.01) }}</p>
                            <p class="stat-label">Hours of Audio</p>
                        </div>

                        <!-- Search -->
                        <div class="search-section">
                            <h3><i class="fas fa-search"></i> Search</h3>
                            <form method="GET" action="/search">
                                <div class="mb-3">
                                    <input type="text" class="form-control" name="q" 
                                           placeholder="Search in Urdu or English..." 
                                           value="{{ search_query }}">
                                </div>
                                <div class="row mb-3">
                                    <div class="col-6">
                                        <select class="form-control form-select">
                                            <option>All Sources</option>
                                            <option>News Channel</option>
                                        </select>
                                    </div>
                                    <div class="col-6">
                                        <input type="date" class="form-control" name="start_date">
                                    </div>
                                </div>
                                <div class="row mb-3">
                                    <div class="col-12">
                                        <input type="date" class="form-control" name="end_date">
                                    </div>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">
                                    <i class="fas fa-search me-2"></i>Search
                                </button>
                            </form>
                        </div>

                        <!-- Trending Keywords -->
                        <div class="filters-section">
                            <h3><i class="fas fa-hashtag"></i> Trending Keywords</h3>
                            <div class="trending-keywords">
                                <a href="#" class="keyword-tag">(1) اہم خبر</a>
                                <a href="#" class="keyword-tag">(1) عاجل</a>
                                <a href="#" class="keyword-tag">(1) تازہ</a>
                                <a href="#" class="keyword-tag">(1) بریکنگ</a>
                                <a href="#" class="keyword-tag">(1) خبریں</a>
                                <a href="#" class="keyword-tag">(1) اطلاعات</a>
                            </div>
                        </div>

                        <!-- Quick Filters -->
                        <div class="filters-section">
                            <h3><i class="fas fa-filter"></i> Quick Filters</h3>
                            <div class="quick-filters">
                                <button class="btn" onclick="filterTime('1h')">Last 1 Hour</button>
                                <button class="btn" onclick="filterTime('6h')">Last 6 Hours</button>
                                <button class="btn active" onclick="filterTime('24h')">Last 24 Hours</button>
                            </div>
                        </div>

                        <!-- Channel Status (only show when multi-channel is active) -->
                        <div class="filters-section" id="channel-status-section" style="display: none;">
                            <h3><i class="fas fa-broadcast-tower"></i> Channel Status</h3>
                            <div id="channel-status-container">
                                <div class="text-center text-muted">
                                    <div class="spinner-border spinner-border-sm" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    <small class="d-block mt-1">Loading channel status...</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Content Area -->
                <div class="col-lg-9">
                    <div class="content-area">
                        <!-- Navigation Tabs -->
                        <ul class="nav nav-tabs" role="tablist">
                            <li class="nav-item">
                                <a class="nav-link active" data-bs-toggle="tab" href="#live-monitor">
                                    <i class="fas fa-broadcast-tower me-2"></i>Live Monitor
                                </a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" data-bs-toggle="tab" href="#ocr-results">
                                    <i class="fas fa-eye me-2"></i>OCR Results
                                </a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" data-bs-toggle="tab" href="#transcriptions">
                                    <i class="fas fa-microphone me-2"></i>Transcriptions
                                </a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" data-bs-toggle="tab" href="#historical-analysis">
                                    <i class="fas fa-chart-line me-2"></i>Historical Analysis
                                </a>
                            </li>
                        </ul>

                        <!-- Tab Content -->
                        <div class="tab-content">
                            <!-- Live Monitor Tab -->
                            <div class="tab-pane fade show active" id="live-monitor">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h4><i class="fas fa-broadcast-tower text-danger me-2"></i>Live Stream Activity</h4>
                                    <button class="btn btn-success btn-sm" onclick="clearActivity()">
                                        <i class="fas fa-broom me-2"></i>Clear
                                    </button>
                                </div>

                                <div class="activity-feed timeline">
                                    {% for item in recent_extractions %}
                                    <div class="activity-item timeline-item">
                                        <div class="activity-badge">{{ item.region_name }}</div>
                                        <div class="activity-content">
                                            <div class="activity-text">{{ item.extracted_text[:150] }}{% if item.extracted_text|length > 150 %}...{% endif %}</div>
                                            <div class="activity-meta">
                                                <span>{{ item.timestamp }} • Confidence: {{ "%.1f"|format(item.confidence * 100) }}% • Priority: {{ item.priority }} • Channel: {{ item.channel_name }}</span>
                                                {% if item.screenshot_path %}
                                                <button class="btn btn-sm btn-primary" 
                                                        data-screenshot="{{ item.screenshot_path }}" 
                                                        data-text="{{ item.extracted_text[:100] }}"
                                                        onclick="viewFrame(this.dataset.screenshot, this.dataset.text)">
                                                    <i class="fas fa-image me-1"></i>View Frame
                                                </button>
                                                {% endif %}
                                            </div>
                                        </div>
                                    </div>
                                    {% endfor %}

                                    {% for item in recent_transcriptions %}
                                    <div class="activity-item timeline-item transcription">
                                        <div class="activity-badge transcription">Transcription</div>
                                        <div class="activity-content">
                                            <div class="activity-text">{{ item.transcribed_text[:150] }}{% if item.transcribed_text|length > 150 %}...{% endif %}</div>
                                            <div class="activity-meta">
                                                <span>{{ item.timestamp }} • Duration: {{ "%.1f"|format(item.duration) }}s • Confidence: {{ "%.1f"|format(item.confidence * 100) }}%</span>
                                            </div>
                                        </div>
                                    </div>
                                    {% endfor %}
                                    
                                    {% if not recent_extractions and not recent_transcriptions %}
                                    <div class="text-center text-muted py-5">
                                        <i class="fas fa-broadcast-tower fa-3x mb-3"></i>
                                        <p>No live activity detected. Start monitoring to see real-time updates.</p>
                                    </div>
                                    {% endif %}
                                </div>
                            </div>

                            <!-- OCR Results Tab -->
                            <div class="tab-pane fade" id="ocr-results">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h4><i class="fas fa-eye me-2"></i>OCR Text Extractions</h4>
                                    <div>
                                        <button class="btn btn-primary btn-sm" onclick="loadOCRResults(1)">
                                            <i class="fas fa-sync-alt me-2"></i>Refresh
                                        </button>
                                        <span class="badge bg-secondary ms-2" id="ocrTotalCount">0 results</span>
                                    </div>
                                </div>
                                
                                <!-- Loading Indicator -->
                                <div id="ocrLoading" class="text-center py-4" style="display: none;">
                                    <div class="spinner-border text-primary" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    <p class="mt-2 text-muted">Loading OCR results...</p>
                                </div>
                                
                                <!-- Results Container -->
                                <div class="activity-feed" id="ocrResultsContainer">
                                    <div class="text-center text-muted py-4">
                                        <i class="fas fa-eye fa-2x mb-2"></i>
                                        <p>Click refresh to load OCR results</p>
                                    </div>
                                </div>
                                
                                <!-- Pagination -->
                                <nav id="ocrPagination" class="mt-3" style="display: none;">
                                    <ul class="pagination pagination-sm justify-content-center" id="ocrPaginationList">
                                        <!-- Pagination will be dynamically generated -->
                                    </ul>
                                </nav>
                            </div>

                            <!-- Transcriptions Tab -->
                            <div class="tab-pane fade" id="transcriptions">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h4><i class="fas fa-microphone me-2"></i>Audio Transcriptions</h4>
                                    <div>
                                        <button class="btn btn-primary btn-sm" onclick="loadTranscriptions(1)">
                                            <i class="fas fa-sync-alt me-2"></i>Refresh
                                        </button>
                                        <span class="badge bg-secondary ms-2" id="transcriptionTotalCount">0 results</span>
                                    </div>
                                </div>
                                
                                <!-- Loading Indicator -->
                                <div id="transcriptionLoading" class="text-center py-4" style="display: none;">
                                    <div class="spinner-border text-primary" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    <p class="mt-2 text-muted">Loading transcriptions...</p>
                                </div>
                                
                                <!-- Results Container -->
                                <div class="activity-feed" id="transcriptionResultsContainer">
                                    <div class="text-center text-muted py-4">
                                        <i class="fas fa-microphone fa-2x mb-2"></i>
                                        <p>Click refresh to load transcriptions</p>
                                    </div>
                                </div>
                                
                                <!-- Pagination -->
                                <nav id="transcriptionPagination" class="mt-3" style="display: none;">
                                    <ul class="pagination pagination-sm justify-content-center" id="transcriptionPaginationList">
                                        <!-- Pagination will be dynamically generated -->
                                    </ul>
                                </nav>
                            </div>

                            <!-- Historical Analysis Tab -->
                            <div class="tab-pane fade" id="historical-analysis">
                                <div class="row">
                                    <!-- Analysis Filters -->
                                    <div class="col-lg-3">
                                        <div class="card">
                                            <div class="card-header">
                                                <h6 class="mb-0"><i class="fas fa-filter me-2"></i>Analysis Filters</h6>
                                            </div>
                                            <div class="card-body">
                                                <!-- Date Range Filter -->
                                                <div class="mb-3">
                                                    <label class="form-label">Date Range</label>
                                                    <div class="row">
                                                        <div class="col-6">
                                                            <input type="date" class="form-control form-control-sm" id="startDate" value="{{ (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d') }}">
                                                        </div>
                                                        <div class="col-6">
                                                            <input type="date" class="form-control form-control-sm" id="endDate" value="{{ datetime.now().strftime('%Y-%m-%d') }}">
                                                        </div>
                                                    </div>
                                                </div>

                                                <!-- Channel Filter -->
                                                <div class="mb-3">
                                                    <label class="form-label">Channel</label>
                                                    <select class="form-control form-control-sm" id="channelFilter">
                                                        <option value="">All Channels</option>
                                                        <option value="News Channel 1">News Channel 1</option>
                                                        <option value="News Channel 2">News Channel 2</option>
                                                    </select>
                                                </div>

                                                <!-- Content Type Filter -->
                                                <div class="mb-3">
                                                    <label class="form-label">Content Type</label>
                                                    <select class="form-control form-control-sm" id="contentTypeFilter">
                                                        <option value="">All Types</option>
                                                        <option value="text">Text Extractions</option>
                                                        <option value="audio">Audio Transcriptions</option>
                                                    </select>
                                                </div>

                                                <!-- Confidence Filter -->
                                                <div class="mb-3">
                                                    <label class="form-label">Min Confidence (%)</label>
                                                    <input type="range" class="form-range" id="confidenceFilter" min="0" max="100" value="50">
                                                    <div class="d-flex justify-content-between">
                                                        <small>0%</small>
                                                        <small id="confidenceValue">50%</small>
                                                        <small>100%</small>
                                                    </div>
                                                </div>

                                                <!-- Apply Filters Button -->
                                                <button class="btn btn-primary btn-sm w-100" onclick="applyHistoricalFilters()">
                                                    <i class="fas fa-search me-2"></i>Apply Filters
                                                </button>

                                                <!-- Export Button -->
                                                <button class="btn btn-success btn-sm w-100 mt-2" onclick="exportHistoricalData()">
                                                    <i class="fas fa-download me-2"></i>Export Data
                                                </button>
                                            </div>
                                        </div>

                                        <!-- Quick Stats -->
                                        <div class="card mt-3">
                                            <div class="card-header">
                                                <h6 class="mb-0"><i class="fas fa-chart-bar me-2"></i>Period Summary</h6>
                                            </div>
                                            <div class="card-body">
                                                <div class="text-center">
                                                    <div class="row text-center">
                                                        <div class="col-6">
                                                            <h5 class="text-primary" id="totalExtractions">0</h5>
                                                            <small class="text-muted">Extractions</small>
                                                        </div>
                                                        <div class="col-6">
                                                            <h5 class="text-success" id="totalTranscriptions">0</h5>
                                                            <small class="text-muted">Transcriptions</small>
                                                        </div>
                                                    </div>
                                                    <hr>
                                                    <div class="row text-center">
                                                        <div class="col-6">
                                                            <h6 class="text-warning" id="totalAlerts">0</h6>
                                                            <small class="text-muted">Alerts</small>
                                                        </div>
                                                        <div class="col-6">
                                                            <h6 class="text-info" id="avgConfidence">0%</h6>
                                                            <small class="text-muted">Avg Confidence</small>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Analysis Results -->
                                    <div class="col-lg-9">
                                        <!-- Analysis Tabs -->
                                        <ul class="nav nav-pills nav-fill mb-3">
                                            <li class="nav-item">
                                                <a class="nav-link active" data-bs-toggle="pill" href="#analysis-data">
                                                    <i class="fas fa-database me-2"></i>Data View
                                                </a>
                                            </li>
                                            <li class="nav-item">
                                                <a class="nav-link" data-bs-toggle="pill" href="#analysis-charts">
                                                    <i class="fas fa-chart-area me-2"></i>Analytics
                                                </a>
                                            </li>
                                            <li class="nav-item">
                                                <a class="nav-link" data-bs-toggle="pill" href="#analysis-keywords">
                                                    <i class="fas fa-hashtag me-2"></i>Keywords
                                                </a>
                                            </li>
                                        </ul>

                                        <!-- Analysis Content -->
                                        <div class="tab-content">
                                            <!-- Data View Tab -->
                                            <div class="tab-pane fade show active" id="analysis-data">
                                                <div class="d-flex justify-content-between align-items-center mb-3">
                                                    <h5><i class="fas fa-list me-2"></i>Historical Records</h5>
                                                    <div class="btn-group btn-group-sm">
                                                        <button class="btn btn-outline-primary" onclick="refreshHistoricalData()">
                                                            <i class="fas fa-sync-alt me-1"></i>Refresh
                                                        </button>
                                                        <button class="btn btn-outline-secondary" onclick="toggleDataView()">
                                                            <i class="fas fa-table me-1"></i>Table/List
                                                        </button>
                                                    </div>
                                                </div>

                                                <!-- Loading Indicator -->
                                                <div id="historicalLoading" class="text-center py-4" style="display: none;">
                                                    <div class="spinner-border text-primary" role="status">
                                                        <span class="visually-hidden">Loading...</span>
                                                    </div>
                                                    <p class="mt-2 text-muted">Loading historical data...</p>
                                                </div>

                                                <!-- Table View -->
                                                <div id="tableView" style="display: none;">
                                                    <div class="table-responsive">
                                                        <table class="table table-striped table-hover">
                                                            <thead class="table-dark">
                                                                <tr>
                                                                    <th>Type</th>
                                                                    <th>Content</th>
                                                                    <th>Channel</th>
                                                                    <th>Confidence</th>
                                                                    <th>Timestamp</th>
                                                                    <th>Actions</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody id="historicalTableBody">
                                                                <tr>
                                                                    <td colspan="6" class="text-center text-muted">No data available</td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                </div>

                                                <!-- List View -->
                                                <div id="listView" class="activity-feed">
                                                    <div id="historicalListContent">
                                                        <div class="text-center text-muted py-4">
                                                            <i class="fas fa-database fa-2x mb-2"></i>
                                                            <p>Click "Apply Filters" to load historical data</p>
                                                        </div>
                                                    </div>
                                                </div>

                                                <!-- Pagination -->
                                                <nav id="historicalPagination" class="mt-3" style="display: none;">
                                                    <ul class="pagination pagination-sm justify-content-center">
                                                        <li class="page-item disabled">
                                                            <a class="page-link" href="#" tabindex="-1">Previous</a>
                                                        </li>
                                                        <li class="page-item active">
                                                            <a class="page-link" href="#">1</a>
                                                        </li>
                                                        <li class="page-item disabled">
                                                            <a class="page-link" href="#">Next</a>
                                                        </li>
                                                    </ul>
                                                </nav>
                                            </div>

                                            <!-- Analytics Tab -->
                                            <div class="tab-pane fade" id="analysis-charts">
                                                <h5><i class="fas fa-chart-area me-2"></i>Analytics Dashboard</h5>
                                                <div class="row">
                                                    <div class="col-md-6">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Activity Over Time</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <canvas id="activityChart" width="400" height="200"></canvas>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="col-md-6">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Channel Distribution</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <canvas id="channelChart" width="400" height="200"></canvas>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div class="row mt-3">
                                                    <div class="col-md-6">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Confidence Distribution</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <canvas id="confidenceChart" width="400" height="200"></canvas>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="col-md-6">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Content Types</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <canvas id="contentTypeChart" width="400" height="200"></canvas>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>

                                            <!-- Keywords Tab -->
                                            <div class="tab-pane fade" id="analysis-keywords">
                                                <h5><i class="fas fa-hashtag me-2"></i>Keyword Analysis</h5>
                                                <div class="row">
                                                    <div class="col-md-8">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Top Keywords</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <div id="keywordCloud" style="min-height: 300px; text-align: center;">
                                                                    <p class="text-muted">Load data to see keyword cloud</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="col-md-4">
                                                        <div class="card">
                                                            <div class="card-header">
                                                                <h6 class="mb-0">Keyword Statistics</h6>
                                                            </div>
                                                            <div class="card-body">
                                                                <div id="keywordStats">
                                                                    <div class="text-center text-muted">
                                                                        <i class="fas fa-hashtag fa-2x mb-2"></i>
                                                                        <p>No data available</p>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Frame Viewer Modal -->
    <div class="modal fade" id="frameModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="frameModalTitle">Frame View</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center">
                    <img id="frameImage" src="" alt="Frame" style="max-width: 100%; height: auto;">
                    <div class="mt-3">
                        <p id="frameText" style="font-family: 'Noto Nastaliq Urdu', serif; font-size: 1.2rem; direction: rtl;"></p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Monitor Control Button -->
    <div class="monitor-controls">
        {% if monitor_running %}
        <button class="btn btn-stop btn-monitor" onclick="controlMonitor('stop')">
            <i class="fas fa-stop me-2"></i>Stop Monitor
        </button>
        {% else %}
        <button class="btn btn-start btn-monitor" onclick="controlMonitor('start')">
            <i class="fas fa-play me-2"></i>Start Monitor
        </button>
        {% endif %}
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Disable any Socket.IO attempts
        window.io = function() { return { on: function() {}, emit: function() {} }; };
        
        function viewFrame(imagePath, text) {
            // Extract filename from path (handle both backslash and forward slash)
            let filename = imagePath;
            
            // Handle Windows paths with backslashes
            if (filename.includes('\\')) {
                const parts = filename.split('\\');
                filename = parts[parts.length - 1];
            } else if (filename.includes('/')) {
                const parts = filename.split('/');
                filename = parts[parts.length - 1];
            }
            
            document.getElementById('frameImage').src = '/screenshots/' + filename;
            document.getElementById('frameText').textContent = text || '';
            
            // Extract frame number from filename for title
            const frameNum = filename.split('_')[0] || 'Unknown';
            document.getElementById('frameModalTitle').textContent = 'Frame #' + frameNum;
            
            const modal = new bootstrap.Modal(document.getElementById('frameModal'));
            modal.show();
        }
        
        function controlMonitor(action) {
            const button = document.querySelector('.btn-monitor');
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            button.disabled = true;

            fetch(`/api/monitor/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    multi_channel: true  // Use multi-channel monitoring by default
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setTimeout(() => location.reload(), 1000);
                } else {
                    alert('Error: ' + data.error);
                    button.innerHTML = originalText;
                    button.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Connection error. Please check if the server is running.');
                button.innerHTML = originalText;
                button.disabled = false;
            });
        }

        // Function to load channel status
        function loadChannelStatus() {
            fetch('/api/monitor/status')
            .then(response => response.json())
            .then(data => {
                if (data.multi_channel && data.channel_status) {
                    updateChannelStatusDisplay(data.channel_status);
                }
            })
            .catch(error => {
                console.error('Error loading channel status:', error);
            });
        }

        // Function to update channel status display
        function updateChannelStatusDisplay(channelStatus) {
            const container = document.getElementById('channel-status-container');
            const section = document.getElementById('channel-status-section');

            if (!channelStatus.channels || Object.keys(channelStatus.channels).length === 0) {
                section.style.display = 'none';
                return;
            }

            section.style.display = 'block';

            let html = '';
            for (const [channelId, channel] of Object.entries(channelStatus.channels)) {
                const statusClass = channel.running ? 'success-color' : 'danger-color';
                const statusIcon = channel.running ? 'fas fa-circle' : 'far fa-circle';
                const statusText = channel.running ? 'Running' : 'Stopped';

                html += `
                    <div class="channel-item mb-2 p-2 rounded" style="background: ${channel.running ? 'rgba(5, 150, 105, 0.1)' : 'rgba(220, 38, 38, 0.1)'}">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <strong style="font-size: 0.8rem;">${channel.name}</strong>
                            <span class="status-indicator" style="font-size: 0.7rem;">
                                <i class="${statusIcon} me-1" style="color: var(--${statusClass})"></i>
                                ${statusText}
                            </span>
                        </div>
                        <div class="channel-stats" style="font-size: 0.7rem; color: #6B7280;">
                            <span>OCR: ${channel.text_extractions}</span>
                            <span>Audio: ${channel.audio_transcriptions}</span>
                            <span>Alerts: ${channel.alerts_triggered}</span>
                        </div>
                    </div>
                `;
            }

            container.innerHTML = html;
        }

        // Load channel status every 5 seconds
        setInterval(loadChannelStatus, 5000);

        // Initial load of channel status
        loadChannelStatus();
        
        function clearActivity() {
            if (confirm('Clear all activity feed?')) {
                // This would clear the activity in a real implementation
                location.reload();
            }
        }
        
        function filterTime(period) {
            // Remove active class from all buttons
            document.querySelectorAll('.quick-filters .btn').forEach(btn => btn.classList.remove('active'));
            // Add active class to clicked button
            event.target.classList.add('active');
            
            // In a real implementation, this would filter the results
            console.log('Filtering by:', period);
        }
        
        // Auto-refresh data every 30 seconds (without full page reload)
        let autoRefreshInterval = null;
        let isHistoricalTabActive = false;
        
        function startAutoRefresh() {
            if (autoRefreshInterval) return; // Already running
            
            autoRefreshInterval = setInterval(() => {
                // Only refresh if not on historical tab to avoid interrupting analysis
                if (!isHistoricalTabActive) {
                    // Refresh live monitor data without full page reload
                    fetch('/api/monitor/status')
                        .then(response => response.json())
                        .then(data => {
                            // Update status indicator
                            const statusDot = document.querySelector('.status-dot');
                            if (statusDot) {
                                if (data.running) {
                                    statusDot.classList.add('connected');
                                } else {
                                    statusDot.classList.remove('connected');
                                }
                            }
                            // Update channel status if multi-channel
                            if (data.multi_channel && data.channel_status) {
                                updateChannelStatusDisplay(data.channel_status);
                            }
                        })
                        .catch(error => console.log('Auto-refresh error:', error));
                }
            }, 30000); // Every 30 seconds instead of 10
        }
        
        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        }
        
        // Track when historical tab is active
        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', function(e) {
                isHistoricalTabActive = e.target.getAttribute('href') === '#historical-analysis';
            });
        });
        
        // Start auto-refresh
        startAutoRefresh();

        // Historical Analysis Functions
        let currentHistoricalData = [];
        let currentViewMode = 'list'; // 'list' or 'table'
        let chartInstances = {}; // Store chart instances to destroy them later
        let isLoadingHistoricalData = false; // Prevent concurrent requests

        // Apply historical filters
        function applyHistoricalFilters() {
            if (isLoadingHistoricalData) {
                console.log('Already loading data, please wait...');
                return;
            }
            
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const channel = document.getElementById('channelFilter').value;
            const contentType = document.getElementById('contentTypeFilter').value;
            const minConfidence = document.getElementById('confidenceFilter').value;

            loadHistoricalData(startDate, endDate, channel, contentType, minConfidence);
        }

        // Load historical data
        function loadHistoricalData(startDate, endDate, channel, contentType, minConfidence) {
            if (isLoadingHistoricalData) return;
            
            isLoadingHistoricalData = true;
            const loadingEl = document.getElementById('historicalLoading');
            const listView = document.getElementById('listView');
            
            if (loadingEl) loadingEl.style.display = 'block';

            const params = new URLSearchParams({
                start_date: startDate || '',
                end_date: endDate || '',
                channel: channel || '',
                content_type: contentType || '',
                min_confidence: minConfidence / 100
            });

            fetch(`/api/historical/data?${params}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (loadingEl) loadingEl.style.display = 'none';
                    isLoadingHistoricalData = false;
                    
                    if (!Array.isArray(data)) {
                        throw new Error('Invalid data format received');
                    }
                    
                    currentHistoricalData = data;
                    updateHistoricalDisplay(data);
                    updateHistoricalStats(data);
                    updateAnalyticsCharts(data);
                    updateKeywordAnalysis(data);
                })
                .catch(error => {
                    console.error('Error loading historical data:', error);
                    if (loadingEl) loadingEl.style.display = 'none';
                    isLoadingHistoricalData = false;
                    
                    // Show user-friendly error message
                    if (listView) {
                        listView.innerHTML = `
                            <div class="text-center text-danger py-4">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <p>Error loading historical data: ${error.message}</p>
                                <button class="btn btn-sm btn-primary" onclick="refreshHistoricalData()">
                                    <i class="fas fa-sync-alt me-1"></i>Retry
                                </button>
                            </div>
                        `;
                    }
                });
        }

        // Update historical display
        function updateHistoricalDisplay(data) {
            const listView = document.getElementById('listView');
            const tableView = document.getElementById('tableView');
            const tableBody = document.getElementById('historicalTableBody');

            if (data.length === 0) {
                listView.innerHTML = '<div class="text-center text-muted py-4"><i class="fas fa-database fa-2x mb-2"></i><p>No data found for selected filters</p></div>';
                tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No data found for selected filters</td></tr>';
                return;
            }

            // Update list view
            let listHtml = '';
            data.forEach(item => {
                const typeIcon = item.content_type === 'text' ? 'fas fa-eye' : 'fas fa-microphone';
                const typeBadge = item.content_type === 'text' ? 'OCR' : 'Audio';
                const typeClass = item.content_type === 'text' ? 'primary' : 'success';

                listHtml += `
                    <div class="activity-item">
                        <div class="activity-badge bg-${typeClass}">${typeBadge}</div>
                        <div class="activity-content">
                            <div class="activity-text">${item.content}</div>
                            <div class="activity-meta">
                                <span>${item.channel_name} • ${item.timestamp} • Confidence: ${Math.round(item.confidence * 100)}%</span>
                            </div>
                        </div>
                    </div>
                `;
            });
            listView.innerHTML = listHtml;

            // Update table view
            let tableHtml = '';
            data.forEach(item => {
                const typeIcon = item.content_type === 'text' ? 'eye' : 'microphone';
                tableHtml += `
                    <tr>
                        <td><i class="fas fa-${typeIcon} me-1"></i>${item.content_type === 'text' ? 'Text' : 'Audio'}</td>
                        <td>${item.content.length > 100 ? item.content.substring(0, 100) + '...' : item.content}</td>
                        <td>${item.channel_name}</td>
                        <td>${Math.round(item.confidence * 100)}%</td>
                        <td>${item.timestamp}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary" onclick="viewHistoricalItem('${item.id}', '${item.content_type}')">
                                <i class="fas fa-search me-1"></i>View
                            </button>
                        </td>
                    </tr>
                `;
            });
            tableBody.innerHTML = tableHtml;

            // Show pagination if needed
            updatePagination(data.length);
        }

        // Update historical statistics
        function updateHistoricalStats(data) {
            const textExtractions = data.filter(item => item.content_type === 'text').length;
            const transcriptions = data.filter(item => item.content_type === 'audio').length;
            const alerts = data.filter(item => item.alerts).length;
            const avgConfidence = data.length > 0 ?
                data.reduce((sum, item) => sum + item.confidence, 0) / data.length : 0;

            document.getElementById('totalExtractions').textContent = textExtractions;
            document.getElementById('totalTranscriptions').textContent = transcriptions;
            document.getElementById('totalAlerts').textContent = alerts;
            document.getElementById('avgConfidence').textContent = `${Math.round(avgConfidence * 100)}%`;
        }

        // Update analytics charts
        function updateAnalyticsCharts(data) {
            // Destroy existing chart instances to prevent memory leaks
            if (chartInstances.activityChart) {
                chartInstances.activityChart.destroy();
            }
            if (chartInstances.channelChart) {
                chartInstances.channelChart.destroy();
            }
            if (chartInstances.confidenceChart) {
                chartInstances.confidenceChart.destroy();
            }
            if (chartInstances.contentTypeChart) {
                chartInstances.contentTypeChart.destroy();
            }
            
            if (data.length === 0) {
                console.log('No data to display in charts');
                return;
            }
            
            // Activity over time chart
            const dailyActivity = {};
            data.forEach(item => {
                const date = item.timestamp.split(' ')[0];
                if (!dailyActivity[date]) {
                    dailyActivity[date] = { text: 0, audio: 0 };
                }
                dailyActivity[date][item.content_type]++;
            });

            const ctx1 = document.getElementById('activityChart');
            if (!ctx1) return;
            
            chartInstances.activityChart = new Chart(ctx1.getContext('2d'), {
                type: 'line',
                data: {
                    labels: Object.keys(dailyActivity),
                    datasets: [{
                        label: 'Text Extractions',
                        data: Object.values(dailyActivity).map(d => d.text),
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4
                    }, {
                        label: 'Audio Transcriptions',
                        data: Object.values(dailyActivity).map(d => d.audio),
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });

            // Channel distribution
            const channelDist = {};
            data.forEach(item => {
                channelDist[item.channel_name] = (channelDist[item.channel_name] || 0) + 1;
            });

            const ctx2 = document.getElementById('channelChart');
            if (!ctx2) return;
            
            chartInstances.channelChart = new Chart(ctx2.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(channelDist),
                    datasets: [{
                        data: Object.values(channelDist),
                        backgroundColor: ['#007bff', '#28a745', '#ffc107', '#dc3545']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // Confidence distribution
            const confidenceRanges = { '0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0 };
            data.forEach(item => {
                const conf = Math.floor(item.confidence * 100);
                if (conf < 25) confidenceRanges['0-25%']++;
                else if (conf < 50) confidenceRanges['25-50%']++;
                else if (conf < 75) confidenceRanges['50-75%']++;
                else confidenceRanges['75-100%']++;
            });

            const ctx3 = document.getElementById('confidenceChart');
            if (!ctx3) return;
            
            chartInstances.confidenceChart = new Chart(ctx3.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: Object.keys(confidenceRanges),
                    datasets: [{
                        label: 'Records',
                        data: Object.values(confidenceRanges),
                        backgroundColor: '#6f42c1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true } }
                }
            });

            // Content types
            const contentTypes = { text: 0, audio: 0 };
            data.forEach(item => {
                contentTypes[item.content_type]++;
            });

            const ctx4 = document.getElementById('contentTypeChart');
            if (!ctx4) return;
            
            chartInstances.contentTypeChart = new Chart(ctx4.getContext('2d'), {
                type: 'pie',
                data: {
                    labels: ['Text Extractions', 'Audio Transcriptions'],
                    datasets: [{
                        data: [contentTypes.text, contentTypes.audio],
                        backgroundColor: ['#007bff', '#28a745']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        // Update keyword analysis
        function updateKeywordAnalysis(data) {
            // Simple keyword extraction (word frequency)
            const keywordFreq = {};
            data.forEach(item => {
                const words = item.content.toLowerCase().split(/\s+/);
                words.forEach(word => {
                    if (word.length > 3) { // Only words longer than 3 characters
                        keywordFreq[word] = (keywordFreq[word] || 0) + 1;
                    }
                });
            });

            // Sort by frequency
            const sortedKeywords = Object.entries(keywordFreq)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 20);

            // Update keyword cloud (simple text display)
            let keywordHtml = '<div class="d-flex flex-wrap gap-2">';
            sortedKeywords.forEach(([word, freq]) => {
                const size = Math.max(12, Math.min(24, 10 + freq * 2));
                keywordHtml += `<span class="badge bg-light text-dark" style="font-size: ${size}px;">${word} (${freq})</span>`;
            });
            keywordHtml += '</div>';
            document.getElementById('keywordCloud').innerHTML = keywordHtml;

            // Update keyword stats
            const totalKeywords = sortedKeywords.length;
            const topKeyword = sortedKeywords[0] ? sortedKeywords[0][0] : 'N/A';
            const avgFreq = sortedKeywords.length > 0 ?
                sortedKeywords.reduce((sum, [, freq]) => sum + freq, 0) / sortedKeywords.length : 0;

            document.getElementById('keywordStats').innerHTML = `
                <div class="mb-2">
                    <strong>Total Unique Keywords:</strong><br>
                    <span class="h5 text-primary">${totalKeywords}</span>
                </div>
                <div class="mb-2">
                    <strong>Top Keyword:</strong><br>
                    <span class="text-success">"${topKeyword}"</span>
                </div>
                <div class="mb-2">
                    <strong>Avg Frequency:</strong><br>
                    <span class="text-info">${Math.round(avgFreq * 10) / 10}</span>
                </div>
            `;
        }

        // Toggle between list and table view
        function toggleDataView() {
            const listView = document.getElementById('listView');
            const tableView = document.getElementById('tableView');

            if (currentViewMode === 'list') {
                listView.style.display = 'none';
                tableView.style.display = 'block';
                currentViewMode = 'table';
            } else {
                listView.style.display = 'block';
                tableView.style.display = 'none';
                currentViewMode = 'list';
            }
        }

        // Refresh historical data
        function refreshHistoricalData() {
            applyHistoricalFilters();
        }

        // Export historical data
        function exportHistoricalData() {
            if (currentHistoricalData.length === 0) {
                alert('No data to export');
                return;
            }

            const dataStr = JSON.stringify(currentHistoricalData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `news_monitor_historical_${new Date().toISOString().split('T')[0]}.json`;
            link.click();
            URL.revokeObjectURL(url);
        }

        // View historical item details
        function viewHistoricalItem(id, contentType) {
            // This would open a modal with full details
            console.log('View item:', id, contentType);
            // Implementation would depend on available data structure
        }

        // Update pagination
        function updatePagination(totalItems) {
            const pagination = document.getElementById('historicalPagination');
            if (totalItems > 50) { // Show pagination if more than 50 items
                pagination.style.display = 'block';
            } else {
                pagination.style.display = 'none';
            }
        }

        // Update confidence filter display value
        document.getElementById('confidenceFilter').addEventListener('input', function() {
            document.getElementById('confidenceValue').textContent = this.value + '%';
        });

        // Load initial historical data on tab show
        const historicalTabLink = document.querySelector('[href="#historical-analysis"]');
        if (historicalTabLink) {
            historicalTabLink.addEventListener('shown.bs.tab', function(e) {
                // Only load if we haven't loaded data yet
                if (currentHistoricalData.length === 0 && !isLoadingHistoricalData) {
                    // Load data for the last 7 days by default
                    const endDate = new Date().toISOString().split('T')[0];
                    const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

                    // Set default values in form
                    const startDateEl = document.getElementById('startDate');
                    const endDateEl = document.getElementById('endDate');
                    
                    if (startDateEl) startDateEl.value = startDate;
                    if (endDateEl) endDateEl.value = endDate;

                    // Load initial data with a small delay to ensure DOM is ready
                    setTimeout(() => {
                        loadHistoricalData(startDate, endDate, '', '', 50);
                    }, 100);
                }
            });
        }
        
        // OCR Results Pagination
        let isLoadingOCR = false;
        let ocrCurrentPage = 1;
        let ocrTotalPages = 1;
        const ocrPerPage = 50;
        
        function loadOCRResults(page = 1) {
            if (isLoadingOCR) return;
            
            isLoadingOCR = true;
            ocrCurrentPage = page;
            
            const loadingEl = document.getElementById('ocrLoading');
            const containerEl = document.getElementById('ocrResultsContainer');
            
            if (loadingEl) loadingEl.style.display = 'block';
            if (containerEl) containerEl.style.display = 'none';
            
            fetch(`/api/ocr/results?page=${page}&per_page=${ocrPerPage}`)
                .then(response => {
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    return response.json();
                })
                .then(data => {
                    if (loadingEl) loadingEl.style.display = 'none';
                    if (containerEl) containerEl.style.display = 'block';
                    isLoadingOCR = false;
                    
                    displayOCRResults(data.results);
                    updateOCRPagination(data.total, data.page, data.total_pages);
                })
                .catch(error => {
                    console.error('Error loading OCR results:', error);
                    if (loadingEl) loadingEl.style.display = 'none';
                    if (containerEl) {
                        containerEl.style.display = 'block';
                        containerEl.innerHTML = `
                            <div class="text-center text-danger py-4">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <p>Error loading OCR results: ${error.message}</p>
                                <button class="btn btn-sm btn-primary" onclick="loadOCRResults(${page})">
                                    <i class="fas fa-sync-alt me-1"></i>Retry
                                </button>
                            </div>
                        `;
                    }
                    isLoadingOCR = false;
                });
        }
        
        function displayOCRResults(results) {
            const container = document.getElementById('ocrResultsContainer');
            if (!container) return;
            
            if (results.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-eye fa-2x mb-2"></i>
                        <p>No OCR results found</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            results.forEach((item, index) => {
                const itemId = `ocr-item-${index}`;
                const escapedText = item.extracted_text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const previewText = item.extracted_text.substring(0, 100).replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                html += `
                    <div class="activity-item" id="${itemId}">
                        <div class="activity-badge">${item.region_name}</div>
                        <div class="activity-content">
                            <div class="activity-text">${escapedText}</div>
                            <div class="activity-meta">
                                <span>${item.timestamp}</span>
                                <span>Confidence: ${Math.round(item.confidence * 100)}%</span>
                                <span>Channel: ${item.channel_name}</span>
                                ${item.screenshot_path ? `
                                    <button class="btn btn-sm btn-primary" 
                                            data-screenshot="${item.screenshot_path}"
                                            data-text="${previewText}"
                                            onclick="viewFrameFromData(this)"
                                            title="View Frame">
                                        <i class="fas fa-image me-1"></i>View Frame
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }
        
        // Helper function to safely view frame from data attributes
        function viewFrameFromData(button) {
            const screenshot = button.getAttribute('data-screenshot');
            const text = button.getAttribute('data-text');
            if (screenshot) {
                viewFrame(screenshot, text);
            }
        }
        
        function updateOCRPagination(total, currentPage, totalPages) {
            ocrTotalPages = totalPages;
            const countEl = document.getElementById('ocrTotalCount');
            const paginationEl = document.getElementById('ocrPagination');
            const paginationList = document.getElementById('ocrPaginationList');
            
            if (countEl) {
                countEl.textContent = `${total} results`;
            }
            
            if (totalPages <= 1) {
                if (paginationEl) paginationEl.style.display = 'none';
                return;
            }
            
            if (paginationEl) paginationEl.style.display = 'block';
            
            let paginationHtml = '';
            
            // Previous button
            paginationHtml += `
                <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="loadOCRResults(${currentPage - 1}); return false;">
                        <i class="fas fa-chevron-left"></i>
                    </a>
                </li>
            `;
            
            // Page numbers (show max 5 pages)
            const startPage = Math.max(1, currentPage - 2);
            const endPage = Math.min(totalPages, currentPage + 2);
            
            if (startPage > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadOCRResults(1); return false;">1</a></li>`;
                if (startPage > 2) paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
            
            for (let i = startPage; i <= endPage; i++) {
                paginationHtml += `
                    <li class="page-item ${i === currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="loadOCRResults(${i}); return false;">${i}</a>
                    </li>
                `;
            }
            
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadOCRResults(${totalPages}); return false;">${totalPages}</a></li>`;
            }
            
            // Next button
            paginationHtml += `
                <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="loadOCRResults(${currentPage + 1}); return false;">
                        <i class="fas fa-chevron-right"></i>
                    </a>
                </li>
            `;
            
            if (paginationList) paginationList.innerHTML = paginationHtml;
        }
        
        // Transcriptions Pagination
        let isLoadingTranscriptions = false;
        let transcriptionCurrentPage = 1;
        let transcriptionTotalPages = 1;
        const transcriptionPerPage = 50;
        
        function loadTranscriptions(page = 1) {
            if (isLoadingTranscriptions) return;
            
            isLoadingTranscriptions = true;
            transcriptionCurrentPage = page;
            
            const loadingEl = document.getElementById('transcriptionLoading');
            const containerEl = document.getElementById('transcriptionResultsContainer');
            
            if (loadingEl) loadingEl.style.display = 'block';
            if (containerEl) containerEl.style.display = 'none';
            
            fetch(`/api/transcriptions/results?page=${page}&per_page=${transcriptionPerPage}`)
                .then(response => {
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    return response.json();
                })
                .then(data => {
                    if (loadingEl) loadingEl.style.display = 'none';
                    if (containerEl) containerEl.style.display = 'block';
                    isLoadingTranscriptions = false;
                    
                    displayTranscriptions(data.results);
                    updateTranscriptionPagination(data.total, data.page, data.total_pages);
                })
                .catch(error => {
                    console.error('Error loading transcriptions:', error);
                    if (loadingEl) loadingEl.style.display = 'none';
                    if (containerEl) {
                        containerEl.style.display = 'block';
                        containerEl.innerHTML = `
                            <div class="text-center text-danger py-4">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <p>Error loading transcriptions: ${error.message}</p>
                                <button class="btn btn-sm btn-primary" onclick="loadTranscriptions(${page})">
                                    <i class="fas fa-sync-alt me-1"></i>Retry
                                </button>
                            </div>
                        `;
                    }
                    isLoadingTranscriptions = false;
                });
        }
        
        function displayTranscriptions(results) {
            const container = document.getElementById('transcriptionResultsContainer');
            if (!container) return;
            
            if (results.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-microphone fa-2x mb-2"></i>
                        <p>No transcriptions found</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            results.forEach((item, index) => {
                const itemId = `transcription-item-${index}`;
                const escapedText = item.transcribed_text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const escapedChannel = item.channel_name.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                
                html += `
                    <div class="activity-item transcription" id="${itemId}">
                        <div class="activity-badge transcription">Audio</div>
                        <div class="activity-content">
                            <div class="activity-text">${escapedText}</div>
                            <div class="activity-meta">
                                <span>${item.timestamp}</span>
                                <span>Duration: ${item.duration ? item.duration.toFixed(1) : 0}s</span>
                                <span>Confidence: ${Math.round(item.confidence * 100)}%</span>
                                <span>Channel: ${escapedChannel}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }
        
        function updateTranscriptionPagination(total, currentPage, totalPages) {
            transcriptionTotalPages = totalPages;
            const countEl = document.getElementById('transcriptionTotalCount');
            const paginationEl = document.getElementById('transcriptionPagination');
            const paginationList = document.getElementById('transcriptionPaginationList');
            
            if (countEl) {
                countEl.textContent = `${total} results`;
            }
            
            if (totalPages <= 1) {
                if (paginationEl) paginationEl.style.display = 'none';
                return;
            }
            
            if (paginationEl) paginationEl.style.display = 'block';
            
            let paginationHtml = '';
            
            // Previous button
            paginationHtml += `
                <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="loadTranscriptions(${currentPage - 1}); return false;">
                        <i class="fas fa-chevron-left"></i>
                    </a>
                </li>
            `;
            
            // Page numbers (show max 5 pages)
            const startPage = Math.max(1, currentPage - 2);
            const endPage = Math.min(totalPages, currentPage + 2);
            
            if (startPage > 1) {
                paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadTranscriptions(1); return false;">1</a></li>`;
                if (startPage > 2) paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
            
            for (let i = startPage; i <= endPage; i++) {
                paginationHtml += `
                    <li class="page-item ${i === currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="loadTranscriptions(${i}); return false;">${i}</a>
                    </li>
                `;
            }
            
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) paginationHtml += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
                paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadTranscriptions(${totalPages}); return false;">${totalPages}</a></li>`;
            }
            
            // Next button
            paginationHtml += `
                <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="loadTranscriptions(${currentPage + 1}); return false;">
                        <i class="fas fa-chevron-right"></i>
                    </a>
                </li>
            `;
            
            if (paginationList) paginationList.innerHTML = paginationHtml;
        }
        
        // Auto-load OCR results when tab is shown
        const ocrTabLink = document.querySelector('[href="#ocr-results"]');
        if (ocrTabLink) {
            ocrTabLink.addEventListener('shown.bs.tab', function() {
                if (ocrCurrentPage === 1 && !isLoadingOCR) {
                    loadOCRResults(1);
                }
            });
        }
        
        // Auto-load transcriptions when tab is shown
        const transcriptionTabLink = document.querySelector('[href="#transcriptions"]');
        if (transcriptionTabLink) {
            transcriptionTabLink.addEventListener('shown.bs.tab', function() {
                if (transcriptionCurrentPage === 1 && !isLoadingTranscriptions) {
                    loadTranscriptions(1);
                }
            });
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
        
        # Get recent data - combine from all channels
        recent_extractions = db.search_text_extractions(limit=50)  # Get more to allow filtering
        recent_transcriptions = db.search_audio_transcriptions(limit=25)  # Get more to allow filtering
        recent_alerts = db.get_alerts(is_read=False, limit=5)
        
        # Parse JSON fields in alerts
        for alert in recent_alerts:
            if alert.get('matched_keywords'):
                # Check if it's already a list
                if isinstance(alert['matched_keywords'], str):
                    try:
                        alert['matched_keywords'] = json.loads(alert['matched_keywords'])
                    except (json.JSONDecodeError, TypeError):
                        alert['matched_keywords'] = []
                elif not isinstance(alert['matched_keywords'], list):
                    alert['matched_keywords'] = []
        
        # Check monitor status (handle both single and multi-channel)
        monitor_running = False
        if news_monitor_instance:
            monitor_running = news_monitor_instance.is_running
        
        response = render_template_string(
            MODERN_TEMPLATE,
            stats=stats,
            recent_extractions=recent_extractions,
            recent_transcriptions=recent_transcriptions,
            recent_alerts=recent_alerts,
            monitor_running=monitor_running,
            search_query="",
            datetime=datetime,
            timedelta=timedelta
        )
        
        # Add cache-busting headers
        from flask import make_response
        resp = make_response(response)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
        
    except Exception as e:
        import traceback
        logging.error(f"Error rendering dashboard: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return f"Error loading dashboard: {e}", 500

@app.route('/search')
def search():
    """Search page"""
    try:
        query = request.args.get('q', '').strip()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        results = []
        transcriptions = []
        
        if query:
            results = db.search_text_extractions(query=query, limit=100)  # More results for search
            transcriptions = db.search_audio_transcriptions(query=query, limit=50)  # More results for search
        
        # Get statistics
        stats = db.get_statistics()
        
        # Get recent alerts
        recent_alerts = db.get_alerts(is_read=False, limit=5)
        for alert in recent_alerts:
            if alert.get('matched_keywords'):
                if isinstance(alert['matched_keywords'], str):
                    try:
                        alert['matched_keywords'] = json.loads(alert['matched_keywords'])
                    except (json.JSONDecodeError, TypeError):
                        alert['matched_keywords'] = []
                elif not isinstance(alert['matched_keywords'], list):
                    alert['matched_keywords'] = []
        
        monitor_running = news_monitor_instance and news_monitor_instance.is_running
        
        return render_template_string(
            MODERN_TEMPLATE,
            stats=stats,
            recent_extractions=results,
            recent_transcriptions=transcriptions,
            recent_alerts=recent_alerts,
            monitor_running=monitor_running,
            search_query=query,
            datetime=datetime,
            timedelta=timedelta
        )
        
    except Exception as e:
        import traceback
        logging.error(f"Error in search: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return f"Search error: {e}", 500

# API Routes
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

        # Check if we should use multi-channel monitoring
        use_multi_channel = config.get('multi_channel', True)

        if use_multi_channel:
            # Use multi-channel monitoring
            news_monitor_instance = MultiChannelNewsMonitor()

            # Start monitoring in a separate thread to avoid blocking
            def start_monitor():
                try:
                    news_monitor_instance.start_monitoring()
                except Exception as e:
                    logging.error(f"Error starting multi-channel monitor: {e}")

            monitor_thread = threading.Thread(target=start_monitor, daemon=True)
            monitor_thread.start()

            return jsonify({
                'success': True,
                'message': 'Multi-channel news monitoring started',
                'channels': list(news_monitor_instance.monitors.keys())
            })
        else:
            # Use single channel monitoring (legacy mode)
            rtsp_url = config.get('rtsp_url', 'rtsp://admin:gcs12345@192.168.2.145:554/Streaming/Channels/101')
            channel_name = config.get('channel_name', 'news_channel')

            # Create monitor instance (this will initialize models when needed)
            news_monitor_instance = NewsMonitor(rtsp_url=rtsp_url, channel_name=channel_name)

            # Start monitoring in a separate thread to avoid blocking
            def start_monitor():
                try:
                    news_monitor_instance.start_monitoring()
                except Exception as e:
                    logging.error(f"Error starting monitor: {e}")

            monitor_thread = threading.Thread(target=start_monitor, daemon=True)
            monitor_thread.start()

            return jsonify({
                'success': True,
                'message': 'News monitoring started',
                'channel_name': channel_name
            })

    except Exception as e:
        logging.error(f"Error in start monitor API: {e}")
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

@app.route('/screenshots/<filename>')
def serve_screenshot(filename):
    """Serve screenshot images"""
    from config import STORAGE_CONFIG
    return send_from_directory(STORAGE_CONFIG['screenshots_dir'], filename)

@app.route('/api/analytics/activity')
def api_analytics_activity():
    """Get activity analytics (stub endpoint to prevent 404s)"""
    return jsonify({'activity': [], 'total': 0})

@app.route('/api/analytics/keywords')
def api_analytics_keywords():
    """Get keyword analytics (stub endpoint to prevent 404s)"""
    return jsonify({'keywords': [], 'total': 0})

@app.route('/api/monitor/status')
def api_monitor_status():
    """Get monitor status"""
    try:
        if news_monitor_instance:
            # Check if it's a multi-channel monitor
            if hasattr(news_monitor_instance, 'get_channel_status'):
                # Multi-channel monitor
                return jsonify({
                    'running': news_monitor_instance.is_running,
                    'multi_channel': True,
                    'channel_status': news_monitor_instance.get_channel_status(),
                    'statistics': news_monitor_instance.get_statistics()
                })
            else:
                # Single channel monitor
                return jsonify({
                    'running': news_monitor_instance.is_running,
                    'multi_channel': False,
                    'channel_name': news_monitor_instance.channel_name,
                    'statistics': news_monitor_instance.get_statistics()
                })
        else:
            return jsonify({
                'running': False,
                'multi_channel': False,
                'channel_name': None,
                'statistics': {}
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels')
def api_get_channels():
    """Get available channels configuration"""
    try:
        from config import RTSP_CHANNELS
        return jsonify({
            'channels': RTSP_CHANNELS,
            'default_url': RTSP_CHANNELS.get('channel_1', {}).get('rtsp_url', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/<channel_id>/extractions')
def api_get_channel_extractions(channel_id):
    """Get text extractions for a specific channel"""
    try:
        limit = int(request.args.get('limit', 50))
        extractions = db.search_text_extractions(channel_name=channel_id, limit=limit)
        return jsonify({'extractions': extractions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/channels/<channel_id>/transcriptions')
def api_get_channel_transcriptions(channel_id):
    """Get audio transcriptions for a specific channel"""
    try:
        limit = int(request.args.get('limit', 20))
        transcriptions = db.search_audio_transcriptions(channel_name=channel_id, limit=limit)
        return jsonify({'transcriptions': transcriptions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical/data')
def api_historical_data():
    """Get historical data with filters"""
    try:
        # Parse filters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        channel = request.args.get('channel', '')
        content_type = request.args.get('content_type', '')
        min_confidence = float(request.args.get('min_confidence', 0.0))

        # Convert date strings to datetime objects
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                logging.error(f"Invalid start_date format: {start_date_str}")
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                # Set to end of day
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                logging.error(f"Invalid end_date format: {end_date_str}")
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400

        # Get filtered data
        text_extractions = []
        transcriptions = []

        if content_type == '' or content_type == 'text':
            text_extractions = db.search_text_extractions(
                start_date=start_date,
                end_date=end_date,
                channel_name=channel if channel else None,
                min_confidence=min_confidence,
                limit=1000  # Reasonable limit for analysis
            )

        if content_type == '' or content_type == 'audio':
            transcriptions = db.search_audio_transcriptions(
                start_date=start_date,
                end_date=end_date,
                channel_name=channel if channel else None,
                min_confidence=min_confidence,
                limit=1000  # Reasonable limit for analysis
            )

        # Combine and format data
        combined_data = []

        def format_timestamp(ts):
            """Helper to format timestamp from various types"""
            if isinstance(ts, str):
                # Already a string, return as is
                return ts
            elif isinstance(ts, datetime):
                # Convert datetime to string
                return ts.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # Fallback
                return str(ts)

        for extraction in text_extractions:
            combined_data.append({
                'id': extraction['uuid'],
                'content': extraction['extracted_text'],
                'content_type': 'text',
                'channel_name': extraction['channel_name'],
                'confidence': extraction['confidence'],
                'timestamp': format_timestamp(extraction['timestamp']),
                'region_name': extraction['region_name'],
                'priority': extraction['priority']
            })

        for transcription in transcriptions:
            combined_data.append({
                'id': transcription['uuid'],
                'content': transcription['transcribed_text'],
                'content_type': 'audio',
                'channel_name': transcription['channel_name'],
                'confidence': transcription['confidence'],
                'timestamp': format_timestamp(transcription['timestamp']),
                'duration': transcription['duration'],
                'language': transcription['language']
            })

        # Sort by timestamp (most recent first) - string format YYYY-MM-DD HH:MM:SS is naturally sortable
        combined_data.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify(combined_data)

    except Exception as e:
        logging.error(f"Error in historical data API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical/stats')
def api_historical_stats():
    """Get historical statistics"""
    try:
        # Parse filters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        channel = request.args.get('channel', '')

        # Convert date strings to datetime objects
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                logging.error(f"Invalid start_date format: {start_date_str}")
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                logging.error(f"Invalid end_date format: {end_date_str}")
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400

        # Get statistics
        stats = db.get_statistics(start_date, end_date)

        # Add channel-specific stats if requested
        if channel:
            channel_text = db.search_text_extractions(
                start_date=start_date,
                end_date=end_date,
                channel_name=channel,
                limit=1
            )
            channel_audio = db.search_audio_transcriptions(
                start_date=start_date,
                end_date=end_date,
                channel_name=channel,
                limit=1
            )
            stats['channel_specific'] = {
                'text_count': len(channel_text),
                'audio_count': len(channel_audio)
            }

        return jsonify(stats)

    except Exception as e:
        logging.error(f"Error in historical stats API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical/keywords')
def api_historical_keywords():
    """Get keyword analysis for historical data"""
    try:
        # Parse filters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        channel = request.args.get('channel', '')
        limit = int(request.args.get('limit', 20))

        # Convert date strings to datetime objects
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                logging.error(f"Invalid start_date format: {start_date_str}")
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                logging.error(f"Invalid end_date format: {end_date_str}")
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400

        # Get text data for keyword analysis
        text_data = db.search_text_extractions(
            start_date=start_date,
            end_date=end_date,
            channel_name=channel if channel else None,
            limit=2000  # Larger limit for better keyword analysis
        )

        # Simple keyword extraction
        keyword_freq = {}
        for item in text_data:
            words = item['extracted_text'].lower().split()
            for word in words:
                # Filter out short words and common stop words
                if len(word) > 3 and word not in ['that', 'with', 'have', 'this', 'will', 'from', 'they', 'been']:
                    keyword_freq[word] = keyword_freq.get(word, 0) + 1

        # Sort by frequency and return top keywords
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:limit]

        return jsonify({
            'keywords': [{'word': word, 'frequency': freq} for word, freq in top_keywords],
            'total_unique_words': len(keyword_freq),
            'total_words_analyzed': sum(keyword_freq.values())
        })

    except Exception as e:
        logging.error(f"Error in historical keywords API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical/export')
def api_historical_export():
    """Export historical data in various formats"""
    try:
        format_type = request.args.get('format', 'json')  # json, csv
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        channel = request.args.get('channel', '')
        content_type = request.args.get('content_type', '')

        # Get data (reuse existing function)
        # For simplicity, we'll redirect to the data endpoint and let frontend handle export
        return jsonify({
            'message': 'Use /api/historical/data endpoint and export from frontend',
            'recommended_endpoint': '/api/historical/data'
        })

    except Exception as e:
        logging.error(f"Error in historical export API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr/results')
def api_ocr_results():
    """Get paginated OCR results"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 50
        
        # Get total count first
        with db.lock:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM text_extractions")
                total_count = cursor.fetchone()[0]
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get paginated results
        with db.lock:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT uuid, timestamp, region_name, extracted_text, confidence, 
                           priority, screenshot_path, channel_name
                    FROM text_extractions
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (per_page, offset))
                
                columns = ['uuid', 'timestamp', 'region_name', 'extracted_text', 
                          'confidence', 'priority', 'screenshot_path', 'channel_name']
                results = []
                
                for row in cursor.fetchall():
                    record = dict(zip(columns, row))
                    # Format timestamp if it's not already a string
                    if isinstance(record['timestamp'], str):
                        pass  # Already formatted
                    else:
                        record['timestamp'] = record['timestamp']
                    results.append(record)
        
        return jsonify({
            'results': results,
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages
        })
        
    except Exception as e:
        logging.error(f"Error in OCR results API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcriptions/results')
def api_transcription_results():
    """Get paginated transcription results"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 50
        
        # Get total count first
        with db.lock:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM audio_transcriptions")
                total_count = cursor.fetchone()[0]
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get paginated results
        with db.lock:
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT uuid, timestamp, transcribed_text, confidence, 
                           duration, language, channel_name
                    FROM audio_transcriptions
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                """, (per_page, offset))
                
                columns = ['uuid', 'timestamp', 'transcribed_text', 'confidence',
                          'duration', 'language', 'channel_name']
                results = []
                
                for row in cursor.fetchall():
                    record = dict(zip(columns, row))
                    # Format timestamp if it's not already a string
                    if isinstance(record['timestamp'], str):
                        pass  # Already formatted
                    else:
                        record['timestamp'] = record['timestamp']
                    results.append(record)
        
        return jsonify({
            'results': results,
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages
        })
        
    except Exception as e:
        logging.error(f"Error in transcription results API: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🎯 Starting Modern News Monitor Dashboard")
    print("=" * 50)
    print("📺 Professional TVeyes-like Interface")
    print("🔍 Real-time OCR and Transcription")
    print("🚨 Smart Alerts and Notifications")
    print("=" * 50)
    print(f"🌐 Open: http://{WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
    print("=" * 50)
    
    app.run(
        host=WEB_CONFIG['host'],
        port=WEB_CONFIG['port'],
        debug=WEB_CONFIG['debug']
    )