"""
News Monitor Configuration
TVeyes-like solution for Urdu news monitoring
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
UTRNET_DIR = (
    BASE_DIR.parent
    / "UTRNet-High-Resolution-Urdu-Text-Recognition-main"
    / "UTRNet-High-Resolution-Urdu-Text-Recognition-main"
)
WEIGHTS_PATH = UTRNET_DIR / "best_norm_ED.pth"
URDU_GLYPHS_PATH = UTRNET_DIR / "UrduGlyphs.txt"

# RTSP Stream Configuration - Multiple Channels Support
RTSP_CHANNELS = {
    'channel_1': {
        'name': 'News Channel 1',
        'rtsp_url': 'rtsp://admin:gcs12345@192.168.2.145:554/Streaming/Channels/101',
        'enabled': True,
        'priority': 'high'
    },
    'channel_2': {
        'name': 'News Channel 2',
        'rtsp_url': 'rtsp://admin:Admin123.@192.168.2.144:554/Streaming/Channels/401',
        'enabled': True,
        'priority': 'medium'
    }
}

# Default RTSP URL (for backward compatibility)
RTSP_URL = RTSP_CHANNELS['channel_1']['rtsp_url']

# UTRNet Model Configuration
UTRNET_CONFIG = {
    'FeatureExtraction': 'HRNet',
    'SequenceModeling': 'DBiLSTM',
    'Prediction': 'CTC',
    'imgH': 32,
    'imgW': 400,
    'input_channel': 1,
    'output_channel': 32,
    'hidden_size': 256,
    'batch_max_length': 100,
    'num_fiducial': 20,
    'rgb': False,
    'device_id': None
}

# Text Detection Regions (ticker areas, headlines, etc.)
TEXT_REGIONS = {
    'ticker': {
        'name': 'Bottom Ticker',
        'region': (0, 0.8, 1.0, 1.0),  # x1, y1, x2, y2 as fractions of frame
        'priority': 'high',
        'min_confidence': 0.7
    },
    'headline': {
        'name': 'Headline Area',
        'region': (0, 0, 1.0, 0.3),
        'priority': 'medium',
        'min_confidence': 0.6
    },
    'side_text': {
        'name': 'Side Information',
        'region': (0.7, 0.3, 1.0, 0.7),
        'priority': 'low',
        'min_confidence': 0.5
    }
}

# YouTube / web player: only thin ticker strips (not full frame or side panels)
YOUTUBE_TEXT_REGIONS = {
    'youtube_ticker': {
        'name': 'Bottom Ticker',
        'region': (0.0, 0.86, 1.0, 0.99),
        'priority': 'high',
        'min_confidence': 0.72,
    },
    'youtube_top_bar': {
        'name': 'Top Breaking Bar',
        'region': (0.0, 0.0, 1.0, 0.11),
        'priority': 'high',
        'min_confidence': 0.72,
    },
}

# Database Configuration
DATABASE_CONFIG = {
    'type': 'sqlite',
    'path': BASE_DIR / 'data' / 'news_monitor.db',
    'backup_interval': 3600  # seconds
}

# Processing Configuration
PROCESSING_CONFIG = {
    'frame_interval': 2.0,  # Process every 2 seconds
    'batch_size': 4,
    'max_queue_size': 100,
    'ocr_confidence_threshold': 0.5,
    'min_urdu_text_length': 6,
    'min_region_height_px': 22,
    'duplicate_text_threshold': 0.8  # Similarity threshold to avoid duplicates
}

# Speech Recognition Configuration
SPEECH_CONFIG = {
    'enabled': True,
    'model': 'openai/whisper-small',  # Can use wav2vec2-xlsr-53-urdu as well
    'chunk_duration': 30,  # seconds
    'overlap': 5,  # seconds
    'sample_rate': 16000
}

# Alert Configuration
ALERTS_CONFIG = {
    'enabled': True,
    'keywords': ['breaking', 'urgent', 'عاجل', 'خبر', 'اہم'],
    'notification_methods': ['web', 'email', 'webhook'],
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': '',
        'sender_password': '',
        'recipient_emails': []
    }
}

# Web Interface Configuration
WEB_CONFIG = {
    'host': '0.0.0.0',  # Bind to all network interfaces for internet access
    'port': 5000,
    'debug': False,  # Disable debug mode for production
    'secret_key': 'your-secret-key-change-this',
    'max_search_results': 1000,
    'results_per_page': 50
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': {
        'file': {
            'filename': BASE_DIR / 'logs' / 'news_monitor.log',
            'max_bytes': 10485760,  # 10MB
            'backup_count': 5
        },
        'console': {
            'enabled': True
        }
    }
}

# Storage Configuration
STORAGE_CONFIG = {
    'screenshots_dir': BASE_DIR / 'data' / 'screenshots',
    'audio_clips_dir': BASE_DIR / 'data' / 'audio',
    'max_storage_days': 30,  # Keep data for 30 days
    'cleanup_interval': 86400  # Clean up daily
}