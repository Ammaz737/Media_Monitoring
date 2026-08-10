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

# Seed RTSP channels — written to SQLite on first boot, then DB is source of truth.
# Camera 192.168.2.173 — stream IDs 101, 201, ..., 801
DEFAULT_RTSP_CHANNELS = {
    'channel_0': {
        'name': 'News Channel 0',
        # Optional quality hint (app-only): &quality=720|1080|480 or &height=720
        'rtsp_url': 'https://www.youtube.com/watch?v=t3fvgmDDmdc&quality=720',
        'enabled': True,
        'priority': 'high'
    },
    'channel_1': {
        'name': 'News Channel 1',
        'rtsp_url': 'rtsp://admin:Admin123.@192.168.2.173:554/Streaming/Channels/101',
        'enabled': False,
        'priority': 'high'
    },
    'channel_2': {
        'name': 'News Channel 2',
        'rtsp_url': 'rtsp://admin:Admin123.@192.168.2.173:554/Streaming/Channels/201',
        'enabled': False,
        'priority': 'medium'
    },
    'channel_3': {
        'name': 'News Channel 3',
        'rtsp_url': 'rtsp://admin:Admin123.@192.168.2.173:554/Streaming/Channels/301',
        'enabled': False,
        'priority': 'medium'
    },
    'channel_4': {
        'name': 'News Channel 4',
        'rtsp_url': 'rtsp://admin:Admin123.@192.168.2.173:554/Streaming/Channels/401',
        'enabled': False,
        'priority': 'medium'
    },
}

# In-memory cache synced from the `channels` SQLite table at web/monitor startup.
RTSP_CHANNELS = {cid: dict(cfg) for cid, cfg in DEFAULT_RTSP_CHANNELS.items()}

# Default RTSP URL (for backward compatibility)
RTSP_URL = RTSP_CHANNELS['channel_1']['rtsp_url']

# YouTube auth (optional) — needed for private / members-only / age-gated lives
# Export cookies once: browser extension "Get cookies.txt LOCALLY" → save as data/youtube_cookies.txt
# Or set browser name to auto-read (chrome|edge|firefox) — Chrome must be fully closed.
YOUTUBE_COOKIES_FILE = BASE_DIR / "data" / "youtube_cookies.txt"
YOUTUBE_COOKIES_FROM_BROWSER = os.environ.get("YOUTUBE_COOKIES_FROM_BROWSER", "").strip() or None

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
    'frame_interval': 1.0,  # Capture one frame every second
    'batch_size': 4,
    # How many queued frames to OCR per processing tick (1 = steady ~1s cadence)
    'ocr_frames_per_tick': 1,
    'max_queue_size': 100,
    # App-wide floor: discard low-confidence OCR before DB / UI
    'ocr_confidence_threshold': 0.85,
    'min_urdu_text_length': 6,
    # Skip OCR entirely for stub/disabled regions (draw tiny boxes in Settings to ignore)
    'min_region_height_px': 22,
    'min_region_width_px': 80,
    'duplicate_text_threshold': 0.8,  # Similarity threshold to avoid duplicates
    # Soft per-region crop change gate (YouTube compression + RTSP tickers):
    # shrink → grayscale → light blur → mean abs diff vs last crop.
    # Only run UTRNet/Ollama when a ticker/headline crop actually changed.
    'crop_change_enabled': True,
    'crop_change_width': 160,
    'crop_change_height': 32,
    'crop_change_blur': 3,  # odd kernel; 0/1 = no blur
    'crop_change_mean_diff': 2.5,  # 0–255; below = unchanged (ignores stream noise)
    # Re-OCR anyway after this many seconds with no change (catch rare soft-misses)
    'crop_change_force_ocr_sec': 15.0,
    # Save OCR region crops for debugging (raw always; preprocessed when mode != none)
    'save_ocr_crops': True,
    # Crop preprocess before UTRNet / Ollama:
    #   "none"          — raw crop
    #   "clahe_otsu"    — grayscale CLAHE + Otsu (legacy binary enhance)
    #   "clear_text_hd" — upscale + NLMeans denoise + unsharp (color-preserving)
    'ocr_preprocess': 'none',
    # Legacy: if True and ocr_preprocess is "none", behaves like "clahe_otsu"
    'ocr_enhance_crop': False,
}

# Ollama vision OCR fallback for mid-confidence UTRNet results
# Band: utrnet_min <= confidence < utrnet_high → ask Ollama; only keep high-confidence replies
OLLAMA_OCR_CONFIG = {
    'enabled': True,
    'base_url': os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/'),
    # Prefer a vision model that fits beside UTRNet on 16GB (qwen3.6:latest is ~23GB)
    'model': os.environ.get('OLLAMA_OCR_MODEL', 'gemma4:12b'),
    'utrnet_min': 0.85,   # below this → discard (do not call Ollama)
    'utrnet_high': 0.97,  # at/above this → trust UTRNet, skip Ollama
    'save_min_confidence': 0.95,  # only persist Ollama replies at/above this
    # Save crop + metadata when Ollama reply is below save_min (debug / review)
    'save_rejected': True,
    'timeout_sec': 45.0,
    'max_image_width': 1280,
    'jpeg_quality': 100,
    'keep_alive': '10m',
    'num_predict': 120,
    # Disable chain-of-thought so JSON fits in num_predict
    'think': False,
    # Drop refine if another call is in flight (avoid backlog / stall)
    'skip_if_busy': True,
}

# Auto-start RTSP monitoring when Flask boots.
# True = monitoring begins on app start for all enabled DB channels.
# Settings channel toggles choose which channels are eligible; Dashboard Start/Stop still works.
AUTO_START_MONITORING = True

# Speech Recognition Configuration
SPEECH_CONFIG = {
    'enabled': False,
    'model': 'openai/whisper-large-v3-turbo',  # Can use wav2vec2-xlsr-53-urdu as well
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

# Persist Settings UI changes (keywords, etc.) across restarts
RUNTIME_CONFIG_PATH = BASE_DIR / 'data' / 'runtime_config.json'


def load_runtime_config() -> None:
    """Merge saved runtime settings into in-memory config."""
    import json

    if not RUNTIME_CONFIG_PATH.exists():
        return
    try:
        with open(RUNTIME_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        keywords = data.get('alert_keywords')
        if isinstance(keywords, list):
            cleaned = [str(k).strip() for k in keywords if str(k).strip()]
            ALERTS_CONFIG['keywords'] = cleaned
        if 'alerts_enabled' in data:
            ALERTS_CONFIG['enabled'] = bool(data['alerts_enabled'])
        # rtsp_channels_enabled is legacy — channels now live in SQLite
    except Exception:
        pass


def save_runtime_config() -> None:
    """Persist mutable runtime settings to disk."""
    import json

    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'alert_keywords': list(ALERTS_CONFIG.get('keywords', [])),
        'alerts_enabled': bool(ALERTS_CONFIG.get('enabled', True)),
    }
    with open(RUNTIME_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def apply_rtsp_channels(channels: dict) -> None:
    """Replace in-memory RTSP_CHANNELS cache (and default URL) from DB payload."""
    global RTSP_URL
    RTSP_CHANNELS.clear()
    for cid, cfg in (channels or {}).items():
        entry = {
            'name': str(cfg.get('name') or cid),
            'rtsp_url': str(cfg.get('rtsp_url') or ''),
            'enabled': bool(cfg.get('enabled', True)),
            'priority': str(cfg.get('priority') or 'medium'),
        }
        regions = cfg.get('text_regions')
        if isinstance(regions, dict) and regions:
            entry['text_regions'] = regions
        RTSP_CHANNELS[cid] = entry
    if RTSP_CHANNELS:
        first = next(iter(RTSP_CHANNELS.values()))
        RTSP_URL = first.get('rtsp_url') or RTSP_URL
    elif DEFAULT_RTSP_CHANNELS:
        RTSP_URL = next(iter(DEFAULT_RTSP_CHANNELS.values())).get('rtsp_url', RTSP_URL)


def default_text_regions_for_url(url: str = '') -> dict:
    """Return a deep copy of the default region map for a stream URL."""
    import copy
    if url and str(url).lower().startswith(('http://', 'https://', 'yt:')):
        # YouTube detection is more precise in news_monitor; use RTSP defaults here
        # unless clearly a youtube host.
        low = str(url).lower()
        if 'youtube.com' in low or 'youtu.be' in low:
            return copy.deepcopy(YOUTUBE_TEXT_REGIONS)
    return copy.deepcopy(TEXT_REGIONS)


def normalize_text_regions(regions: dict, fallback: dict = None) -> dict:
    """Validate / clamp fractional region boxes; keep known keys + metadata."""
    import copy
    base = copy.deepcopy(fallback or TEXT_REGIONS)
    if not isinstance(regions, dict):
        return base

    out = copy.deepcopy(base)
    for key, cfg in regions.items():
        if not isinstance(cfg, dict):
            continue
        region = cfg.get('region')
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in region]
        except (TypeError, ValueError):
            continue
        x1 = max(0.0, min(1.0, x1))
        y1 = max(0.0, min(1.0, y1))
        x2 = max(0.0, min(1.0, x2))
        y2 = max(0.0, min(1.0, y2))
        if x2 - x1 < 0.02:
            x2 = min(1.0, x1 + 0.02)
        if y2 - y1 < 0.02:
            y2 = min(1.0, y1 + 0.02)
        template = out.get(key) or base.get(key) or {
            'name': str(cfg.get('name') or key),
            'priority': 'medium',
            'min_confidence': 0.6,
        }
        out[key] = {
            'name': str(cfg.get('name') or template.get('name') or key),
            'region': [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)],
            'priority': str(cfg.get('priority') or template.get('priority') or 'medium'),
            'min_confidence': float(
                cfg.get('min_confidence', template.get('min_confidence', 0.6))
            ),
        }
    return out


load_runtime_config()

# Web Interface Configuration
WEB_CONFIG = {
    'host': '0.0.0.0',  # Bind to all network interfaces for internet access
    'port': 5000,
    'debug': False,  # Disable debug mode for production
    'secret_key': 'your-secret-key-change-this',
    'max_search_results': 1000,
    'results_per_page': 1000
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
    # OCR region crops for debugging (raw always; preprocessed when ocr_preprocess != none)
    'ocr_crops_dir': BASE_DIR / 'data' / 'ocr_crops',
    # Mid-band Ollama replies discarded for low confidence / empty text
    'ollama_rejected_dir': BASE_DIR / 'data' / 'ollama_rejected',
    'max_storage_days': 30,  # Keep data for 30 days
    'cleanup_interval': 86400  # Clean up daily
}