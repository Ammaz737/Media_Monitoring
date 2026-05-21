#!/usr/bin/env python3
"""
Production server for News Monitor
Uses Waitress as production WSGI server
"""

import sys
import logging
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

# Setup logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from config import WEB_CONFIG, LOGGING_CONFIG
from database import NewsDatabase, create_indices

def initialize_system():
    """Initialize database and system components"""
    try:
        db = NewsDatabase()
        create_indices()
        logging.info("Database initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        return False

def run_with_waitress():
    """Run with Waitress production server"""
    try:
        from waitress import serve
        from web_app import app, socketio
        
        logging.info("=" * 60)
        logging.info("News Monitor System - Production Mode (Waitress)")
        logging.info("=" * 60)
        logging.info(f"Server starting on {WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
        logging.info(f"Access locally: http://localhost:{WEB_CONFIG['port']}")
        logging.info(f"Access on network: http://192.168.101.96:{WEB_CONFIG['port']}")
        logging.info("Press Ctrl+C to stop the server")
        logging.info("=" * 60)
        
        # Use waitress for production
        serve(
            app,
            host=WEB_CONFIG['host'],
            port=WEB_CONFIG['port'],
            threads=4,
            channel_timeout=120,
            cleanup_interval=30,
            asyncore_use_poll=True
        )
        
    except ImportError:
        logging.warning("Waitress not installed, falling back to Flask development server")
        run_with_flask()
    except Exception as e:
        logging.error(f"Error running production server: {e}")
        return False

def run_with_flask():
    """Fallback to Flask development server"""
    try:
        from web_app import app, socketio
        
        logging.info("=" * 60)
        logging.info("News Monitor System - Development Mode (Flask)")
        logging.info("=" * 60)
        logging.info(f"Server starting on {WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
        logging.info(f"Access locally: http://localhost:{WEB_CONFIG['port']}")
        logging.info(f"Access on network: http://192.168.101.96:{WEB_CONFIG['port']}")
        logging.info("Press Ctrl+C to stop the server")
        logging.info("=" * 60)
        
        if socketio:
            socketio.run(
                app,
                host=WEB_CONFIG['host'],
                port=WEB_CONFIG['port'],
                debug=False,
                use_reloader=False
            )
        else:
            app.run(
                host=WEB_CONFIG['host'],
                port=WEB_CONFIG['port'],
                debug=False,
                use_reloader=False
            )
    except Exception as e:
        logging.error(f"Error running Flask server: {e}")
        return False

if __name__ == '__main__':
    # Initialize system
    if not initialize_system():
        logging.error("Failed to initialize system. Exiting.")
        sys.exit(1)
    
    # Run production server
    run_with_waitress()
