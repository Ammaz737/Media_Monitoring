#!/usr/bin/env python3
"""
Main Entry Point for News Monitor System
TVeyes-like solution for Urdu news monitoring
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import LOGGING_CONFIG, RTSP_URL, RTSP_CHANNELS
from news_monitor import NewsMonitor, MultiChannelNewsMonitor
from database import NewsDatabase, create_indices

try:
    from web_app import app, socketio
except ImportError as e:
    logging.warning(f"Web app import failed: {e}")
    app = None
    socketio = None

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format'],
        handlers=[
            logging.FileHandler(LOGGING_CONFIG['handlers']['file']['filename']),
            logging.StreamHandler() if LOGGING_CONFIG['handlers']['console']['enabled'] else logging.NullHandler()
        ]
    )

def initialize_database():
    """Initialize database and create indices"""
    try:
        db = NewsDatabase()
        create_indices()
        logging.info("Database initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        return False

def run_monitor_only(rtsp_url: str, channel_name: str = "news_channel", multi_channel: bool = False):
    """Run news monitor without web interface"""
    try:
        if multi_channel:
            # Use multi-channel monitoring
            monitor = MultiChannelNewsMonitor()
            monitor.start_monitoring()

            logging.info("Multi-channel news monitor started. Press Ctrl+C to stop.")

            # Keep running until interrupted
            try:
                while monitor.is_running:
                    import time
                    time.sleep(1)

                    # Print statistics every 60 seconds
                    stats = monitor.get_statistics()
                    if stats.get('runtime_seconds', 0) % 60 < 1:
                        logging.info(f"Multi-channel Stats: {stats['text_extractions']} extractions, "
                                   f"{stats['audio_transcriptions']} transcriptions, "
                                   f"{stats['alerts_triggered']} alerts, "
                                   f"{stats['channels_running']}/{stats['channels_total']} channels running")

            except KeyboardInterrupt:
                logging.info("Stopping multi-channel monitor...")
                monitor.stop_monitoring()
        else:
            # Use single channel monitoring (legacy mode)
            monitor = NewsMonitor(rtsp_url=rtsp_url, channel_name=channel_name)
            monitor.start_monitoring()

            logging.info("News monitor started. Press Ctrl+C to stop.")

            # Keep running until interrupted
            try:
                while monitor.is_running:
                    import time
                    time.sleep(1)

                    # Print statistics every 60 seconds
                    stats = monitor.get_statistics()
                    if stats.get('runtime_seconds', 0) % 60 < 1:
                        logging.info(f"Stats: {stats['text_extractions']} extractions, "
                                   f"{stats['audio_transcriptions']} transcriptions, "
                                   f"{stats['alerts_triggered']} alerts")

            except KeyboardInterrupt:
                logging.info("Stopping monitor...")
                monitor.stop_monitoring()

    except Exception as e:
        logging.error(f"Error running monitor: {e}")
        return False

    return True

def run_web_interface():
    """Run web interface with integrated monitor"""
    try:
        if app is None:
            logging.error("Web app not available. Please install required dependencies.")
            return False
            
        from config import WEB_CONFIG
        
        logging.info(f"Starting web interface on {WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
        
        if socketio:
            socketio.run(
                app,
                host=WEB_CONFIG['host'],
                port=WEB_CONFIG['port'],
                debug=WEB_CONFIG['debug'],
                use_reloader=False  # Disable reloader to avoid issues
            )
        else:
            logging.warning("Running without real-time updates (SocketIO disabled)")
            app.run(
                host=WEB_CONFIG['host'],
                port=WEB_CONFIG['port'],
                debug=WEB_CONFIG['debug'],
                use_reloader=False
            )
        
    except Exception as e:
        logging.error(f"Error running web interface: {e}")
        return False
    
    return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="News Monitor - TVeyes-like solution for Urdu news monitoring"
    )
    
    parser.add_argument(
        '--mode',
        choices=['web', 'monitor', 'test'],
        default='web',
        help='Run mode: web interface, monitor only, or test setup'
    )
    
    parser.add_argument(
        '--rtsp-url',
        default=RTSP_URL,
        help='RTSP stream URL'
    )
    
    parser.add_argument(
        '--channel-name',
        default='news_channel',
        help='Channel name for identification'
    )

    parser.add_argument(
        '--multi-channel',
        action='store_true',
        help='Enable multi-channel monitoring'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Override log level if specified
    if args.log_level:
        LOGGING_CONFIG['level'] = args.log_level
    
    # Setup logging
    setup_logging()
    logging.info("News Monitor System Starting...")
    
    # Initialize database
    if not initialize_database():
        logging.error("Failed to initialize database. Exiting.")
        sys.exit(1)
    
    # Run based on mode
    if args.mode == 'test':
        logging.info("Testing system setup...")
        test_system_setup()
        
    elif args.mode == 'monitor':
        logging.info("Running monitor only mode...")
        success = run_monitor_only(args.rtsp_url, args.channel_name, args.multi_channel)
        if not success:
            sys.exit(1)
            
    elif args.mode == 'web':
        logging.info("Running web interface mode...")
        success = run_web_interface()
        if not success:
            sys.exit(1)
    
    logging.info("News Monitor System stopped.")

def test_system_setup():
    """Test system setup and dependencies"""
    logging.info("Testing system setup...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Database connection
    total_tests += 1
    try:
        db = NewsDatabase()
        db.get_statistics()
        logging.info("✓ Database connection test passed")
        tests_passed += 1
    except Exception as e:
        logging.error(f"✗ Database connection test failed: {e}")
    
    # Test 2: UTRNet model loading
    total_tests += 1
    try:
        from utrnet_wrapper import UTRNetPredictor
        predictor = UTRNetPredictor(device='cpu')  # Use CPU for testing
        logging.info("✓ UTRNet model loading test passed")
        predictor.cleanup()
        tests_passed += 1
    except Exception as e:
        logging.error(f"✗ UTRNet model loading test failed: {e}")
    
    # Test 3: Speech transcription
    total_tests += 1
    try:
        from speech_transcription import SpeechTranscriber
        transcriber = SpeechTranscriber(device='cpu')
        logging.info("✓ Speech transcription test passed")
        transcriber.cleanup()
        tests_passed += 1
    except Exception as e:
        logging.error(f"✗ Speech transcription test failed: {e}")
    
    # Test 4: Alert system
    total_tests += 1
    try:
        from alert_system import AlertSystem
        alert_system = AlertSystem(db)
        test_results = alert_system.test_notifications()
        logging.info(f"✓ Alert system test passed: {test_results}")
        alert_system.cleanup()
        tests_passed += 1
    except Exception as e:
        logging.error(f"✗ Alert system test failed: {e}")
    
    # Test 5: RTSP connection (basic test)
    total_tests += 1
    try:
        import cv2
        cap = cv2.VideoCapture(RTSP_URL)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                logging.info("✓ RTSP connection test passed")
                tests_passed += 1
            else:
                logging.warning("✗ RTSP connection test failed: No frame received")
            cap.release()
        else:
            logging.warning("✗ RTSP connection test failed: Cannot open stream")
    except Exception as e:
        logging.error(f"✗ RTSP connection test failed: {e}")
    
    # Summary
    logging.info(f"System setup test results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logging.info("🎉 All tests passed! System is ready to run.")
    elif tests_passed >= total_tests - 1:
        logging.warning("⚠️  Most tests passed. System should work with minor issues.")
    else:
        logging.error("❌ Multiple tests failed. Please check your setup.")

if __name__ == '__main__':
    main()