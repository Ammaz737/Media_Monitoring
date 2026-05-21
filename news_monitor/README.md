# News Monitor System

A comprehensive TVeyes-like solution for monitoring Urdu news channels with real-time text extraction, audio transcription, and intelligent alerts.

## 🌟 Features

### Core Capabilities
- **Real-time RTSP Stream Processing**: Monitor live news channels from RTSP streams
- **Urdu Text Recognition**: Advanced OCR using UTRNet model optimized for Urdu text
- **Audio Transcription**: Offline speech-to-text using Whisper or Wav2Vec2 models
- **Smart Region Detection**: Extract text from specific regions (tickers, headlines, sidebars)
- **Intelligent Alerts**: Keyword-based alerts with multiple notification methods
- **Real-time Dashboard**: Modern web interface with live updates and analytics

### Advanced Features
- **Duplicate Detection**: Smart filtering to avoid redundant content
- **Multi-region Processing**: Separate processing for different screen regions
- **Performance Optimization**: Efficient batch processing and caching
- **Data Storage**: SQLite database with full-text search capabilities
- **Export Capabilities**: Search and export extracted content
- **Multi-channel Support**: Monitor multiple news channels simultaneously

## 🏗️ Architecture

```
news_monitor/
├── config.py              # Configuration settings
├── main.py                # Main entry point
├── news_monitor.py        # Core monitoring system
├── utrnet_wrapper.py      # UTRNet text recognition wrapper
├── speech_transcription.py # Audio transcription module
├── database.py            # Database management
├── alert_system.py        # Alert and notification system
├── web_app.py             # Flask web application
├── templates/
│   └── index.html         # Dashboard template
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites

1. **UTRNet Model Files**
   - Ensure you have the UTRNet model files in the specified directory
   - Required files: `best_norm_ED.pth`, `UrduGlyphs.txt`

2. **System Requirements**
   - Python 3.7+
   - CUDA-compatible GPU (recommended)
   - Minimum 8GB RAM
   - Network access to RTSP streams

### Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd news_monitor
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Settings**
   Edit `config.py` to set your RTSP URL and preferences:
   ```python
   RTSP_URL = "rtsp://your-stream-url"
   ALERTS_CONFIG['keywords'] = ['your', 'keywords', 'here']
   ```

4. **Test Setup**
   ```bash
   python main.py --mode test
   ```

### Usage

#### Web Interface (Recommended)
```bash
python main.py --mode web
```
Then open http://localhost:5000 in your browser.

#### Command Line Only
```bash
python main.py --mode monitor --rtsp-url "your-rtsp-url" --channel-name "channel1"
```

#### Custom Configuration
```bash
python main.py --mode web --log-level DEBUG
```

## 🎛️ Configuration

### RTSP Stream
```python
RTSP_URL = "rtsp://admin:password@ip:port/stream"
```

### Text Detection Regions
```python
TEXT_REGIONS = {
    'ticker': {
        'region': (0, 0.8, 1.0, 1.0),  # Bottom 20% of screen
        'priority': 'high',
        'min_confidence': 0.7
    },
    'headline': {
        'region': (0, 0, 1.0, 0.3),    # Top 30% of screen
        'priority': 'medium',
        'min_confidence': 0.6
    }
}
```

### Alert Keywords
```python
ALERTS_CONFIG = {
    'keywords': ['breaking', 'urgent', 'عاجل', 'خبر', 'اہم'],
    'notification_methods': ['web', 'email'],
    'email_config': {
        'sender_email': 'your-email@gmail.com',
        'recipient_emails': ['alert@yourcompany.com']
    }
}
```

## 📊 Web Dashboard

The web interface provides:

- **Real-time Statistics**: Live counts of extractions, transcriptions, and alerts
- **Activity Monitoring**: View recent text extractions and audio transcriptions
- **Search Interface**: Full-text search across all captured content
- **Alert Management**: View and manage triggered alerts
- **Performance Metrics**: Monitor system performance and queue sizes
- **Control Panel**: Start/stop monitoring from the web interface

### Key Features:
- **Real-time Updates**: WebSocket connections for live data
- **Responsive Design**: Works on desktop and mobile devices
- **RTL Support**: Proper right-to-left text display for Urdu
- **Export Capabilities**: Download search results
- **Multi-language Interface**: Support for Urdu and English

## 🔍 API Endpoints

### Statistics
- `GET /api/statistics` - System statistics
- `GET /api/monitor/status` - Monitor status

### Data Access
- `GET /api/recent-extractions` - Recent text extractions
- `GET /api/recent-transcriptions` - Recent audio transcriptions
- `GET /api/search-text?q=query` - Search text content
- `GET /api/search-audio?q=query` - Search audio transcriptions

### Control
- `POST /api/monitor/start` - Start monitoring
- `POST /api/monitor/stop` - Stop monitoring

### Alerts
- `GET /api/alerts` - Get alerts
- `POST /api/alerts/{uuid}/mark-read` - Mark alert as read

## 🎯 Use Cases

### News Organizations
- Monitor competitor channels
- Track breaking news across multiple sources
- Archive important content for reference
- Generate alerts for specific topics

### Research Institutions
- Content analysis of news coverage
- Linguistic research on Urdu media
- Political discourse tracking
- Media bias analysis

### Government Agencies
- Media monitoring for policy impact
- Crisis communication tracking
- Public sentiment analysis
- Emergency response coordination

## 🛠️ Customization

### Adding New Languages
1. Add character sets to configuration
2. Update text processing functions
3. Configure appropriate speech recognition models

### Custom Text Regions
Define regions in `config.py`:
```python
TEXT_REGIONS['custom_region'] = {
    'name': 'Custom Area',
    'region': (x1, y1, x2, y2),  # Normalized coordinates
    'priority': 'medium',
    'min_confidence': 0.6
}
```

### Alert Customization
Create custom alert handlers in `alert_system.py`:
```python
def custom_notification_handler(self, notification_data):
    # Your custom logic here
    pass
```

## 🔧 Troubleshooting

### Common Issues

1. **RTSP Connection Failed**
   - Check network connectivity
   - Verify RTSP URL format
   - Test with VLC or similar player

2. **UTRNet Model Not Loading**
   - Ensure model files are in correct location
   - Check CUDA installation for GPU usage
   - Verify model file permissions

3. **Poor Text Recognition**
   - Adjust confidence thresholds
   - Review region definitions
   - Check image quality of RTSP stream

4. **High CPU/Memory Usage**
   - Reduce processing frequency
   - Decrease batch sizes
   - Enable GPU acceleration

### Performance Optimization

1. **GPU Acceleration**
   ```python
   UTRNET_CONFIG['device'] = 'cuda'
   SPEECH_CONFIG['device'] = 'cuda'
   ```

2. **Processing Intervals**
   ```python
   PROCESSING_CONFIG['frame_interval'] = 3.0  # Process every 3 seconds
   ```

3. **Queue Management**
   ```python
   PROCESSING_CONFIG['max_queue_size'] = 50
   PROCESSING_CONFIG['batch_size'] = 8
   ```

## 📈 Production Deployment

### Using Gunicorn
```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 web_app:app
```

### Docker Deployment
```dockerfile
FROM python:3.8

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "main.py", "--mode", "web"]
```

### Systemd Service
```ini
[Unit]
Description=News Monitor System
After=network.target

[Service]
Type=simple
User=newsmonitor
WorkingDirectory=/path/to/news_monitor
ExecStart=/usr/bin/python3 main.py --mode web
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **UTRNet**: For the excellent Urdu text recognition model
- **OpenAI Whisper**: For robust speech transcription
- **Bootstrap**: For the responsive web interface
- **Flask-SocketIO**: For real-time web updates

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the configuration examples

---

**Note**: This system is designed for monitoring public news broadcasts. Ensure compliance with local laws and regulations regarding content monitoring and recording.