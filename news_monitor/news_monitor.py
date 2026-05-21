"""
Main News Monitoring System
Real-time processing of RTSP streams for text and audio extraction
"""

import cv2
import logging
import threading
import time
import queue
import hashlib
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

from config import (
    RTSP_CHANNELS, RTSP_URL, TEXT_REGIONS, YOUTUBE_TEXT_REGIONS,
    PROCESSING_CONFIG, STORAGE_CONFIG, ALERTS_CONFIG, SPEECH_CONFIG,
)
from utrnet_wrapper import (
    UTRNetPredictor,
    clean_urdu_text,
    calculate_text_similarity,
    is_plausible_urdu_text,
)
from speech_transcription import RealtimeSpeechTranscriber, extract_audio_from_rtsp, save_audio_chunk
from database import NewsDatabase
from alert_system import AlertSystem
from stream_resolver import (
    resolve_stream_url,
    is_youtube_url,
    ffmpeg_available,
    FfmpegFrameReader,
)

class NewsMonitor:
    """
    Main news monitoring system
    Processes RTSP streams for real-time text and audio extraction
    """
    
    def __init__(self, rtsp_url: str = None, channel_name: str = "news_channel"):
        self.source_url = (rtsp_url or RTSP_URL).strip()
        self.rtsp_url = self.source_url
        self.channel_name = channel_name
        self.stream_error: Optional[str] = None
        
        # Initialize components
        self.utr_predictor = None
        self.speech_transcriber = None
        self.database = NewsDatabase()
        self.alert_system = AlertSystem(self.database)
        
        # Processing state
        self.is_running = False
        self.video_thread = None
        self.audio_thread = None
        self.processing_thread = None
        
        # Queues for processing
        self.frame_queue = queue.Queue(maxsize=PROCESSING_CONFIG['max_queue_size'])
        self.audio_queue = queue.Queue(maxsize=50)
        
        # Statistics and caching
        self.stats = {
            'frames_processed': 0,
            'text_extractions': 0,
            'audio_transcriptions': 0,
            'alerts_triggered': 0,
            'start_time': None,
            'last_frame_time': None,
            'frames_captured': 0,
        }
        
        self.text_cache = {}  # Cache recent text to avoid duplicates
        self.last_frame_hash = None
        
        # Setup directories
        self._setup_directories()
        
        logging.info(f"News monitor initialized for {self.source_url}")
    
    def _setup_directories(self):
        """Create necessary directories"""
        STORAGE_CONFIG['screenshots_dir'].mkdir(parents=True, exist_ok=True)
        STORAGE_CONFIG['audio_clips_dir'].mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent / 'logs').mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent / 'data').mkdir(parents=True, exist_ok=True)
    
    def initialize_models(self):
        """Initialize AI models"""
        try:
            # Initialize UTRNet predictor
            self.utr_predictor = UTRNetPredictor(
                device='cuda',
                batch_size=PROCESSING_CONFIG['batch_size']
            )
            logging.info("UTRNet model initialized successfully")
            
            # Initialize speech transcriber if enabled and available
            if SPEECH_CONFIG.get('enabled', True):
                try:
                    from speech_transcription import WHISPER_AVAILABLE
                    if WHISPER_AVAILABLE:
                        self.speech_transcriber = RealtimeSpeechTranscriber()
                        self.speech_transcriber.start()
                        logging.info("Speech transcription initialized successfully")
                    else:
                        logging.info("Speech transcription disabled - Whisper not available")
                        self.speech_transcriber = None
                except Exception as e:
                    logging.warning(f"Speech transcription disabled: {e}")
                    self.speech_transcriber = None
            
        except Exception as e:
            logging.error(f"Failed to initialize models: {e}")
            raise
    
    def start_monitoring(self):
        """Start the news monitoring process"""
        if self.is_running:
            logging.warning("Monitoring is already running")
            return
        
        try:
            resolved, resolve_err = resolve_stream_url(self.source_url)
            if resolve_err:
                raise RuntimeError(resolve_err)
            self.rtsp_url = resolved

            self.stats.update({
                'frames_processed': 0,
                'frames_captured': 0,
                'text_extractions': 0,
                'audio_transcriptions': 0,
                'alerts_triggered': 0,
                'last_frame_time': None,
            })
            self.last_frame_hash = None
            self._clear_queues()

            self.is_running = True
            self.stats['start_time'] = datetime.now()
            self.stream_error = "Starting video capture…"

            # Video thread first so queue fills while OCR models load (CPU can take 1–2 min)
            self.video_thread = threading.Thread(
                target=self._video_capture_loop, daemon=True, name="video-capture"
            )
            self.video_thread.start()
            logging.info("Video capture thread started")

            def _boot_models_and_processing():
                try:
                    self.stream_error = "Loading OCR models (first start may take 1–2 min)…"
                    self.initialize_models()
                    self.processing_thread = threading.Thread(
                        target=self._processing_loop, daemon=True, name="frame-processing"
                    )
                    self.processing_thread.start()

                    if self.speech_transcriber:
                        self.audio_thread = threading.Thread(
                            target=self._audio_capture_loop, daemon=True, name="audio-capture"
                        )
                        self.audio_thread.start()
                        logging.info("Audio transcription thread started")
                    else:
                        logging.info("Audio transcription disabled - Whisper not available")

                    if self.stats['frames_captured'] > 0:
                        self.stream_error = None
                    else:
                        self.stream_error = "OCR ready — waiting for video frames…"
                    logging.info("OCR processing thread started")
                except Exception as e:
                    logging.error(f"Failed to initialize processing: {e}")
                    self.stream_error = str(e)

            threading.Thread(
                target=_boot_models_and_processing, daemon=True, name="model-boot"
            ).start()

            logging.info("News monitoring started (video capture active)")
            
        except Exception as e:
            logging.error(f"Failed to start monitoring: {e}")
            self.stop_monitoring()
            raise
    
    def stop_monitoring(self):
        """Stop the news monitoring process"""
        if not self.is_running:
            return
        
        logging.info("Stopping news monitoring...")
        
        self.is_running = False
        
        # Wait for threads to finish
        threads = [self.video_thread, self.audio_thread, self.processing_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5.0)
        
        # Clean up models
        if self.utr_predictor:
            self.utr_predictor.cleanup()
        
        if self.speech_transcriber:
            self.speech_transcriber.cleanup()
        
        # Clear queues
        self._clear_queues()
        
        logging.info("News monitoring stopped")
    
    def _refresh_playback_url(self) -> str:
        """Refresh playable URL (YouTube/HLS links expire quickly)."""
        if is_youtube_url(self.source_url):
            resolved, err = resolve_stream_url(self.source_url)
            if err:
                raise RuntimeError(err)
            self.rtsp_url = resolved
            logging.info("Refreshed YouTube stream URL")
        return self.rtsp_url

    def _open_video_capture(self):
        """OpenCV capture for RTSP; ffmpeg pipe for YouTube when ffmpeg is available."""
        url = self._refresh_playback_url() if is_youtube_url(self.source_url) else self.rtsp_url

        if is_youtube_url(self.source_url) and ffmpeg_available():
            reader = FfmpegFrameReader(url)
            reader.open()
            logging.info("Using ffmpeg pipe for YouTube stream")
            return reader

        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open stream: {self.source_url}")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        for _ in range(3):
            cap.grab()
        return cap

    def _read_frame(self, cap):
        if isinstance(cap, FfmpegFrameReader):
            return cap.read()
        return cap.read()

    def _release_capture(self, cap) -> None:
        if cap is None:
            return
        if isinstance(cap, FfmpegFrameReader):
            cap.release()
        else:
            cap.release()

    def _get_text_regions(self) -> Dict:
        """YouTube: ticker strips only. RTSP: broadcast ticker/headline layout."""
        if is_youtube_url(self.source_url):
            return YOUTUBE_TEXT_REGIONS
        return TEXT_REGIONS

    def _clear_queues(self):
        """Clear processing queues"""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
    
    def _video_capture_loop(self):
        """Main video capture loop"""
        cap = None
        last_frame_time = 0
        last_url_refresh = time.time()
        frame_interval = PROCESSING_CONFIG['frame_interval']
        url_refresh_sec = 75 if is_youtube_url(self.source_url) else 0
        
        try:
            cap = self._open_video_capture()
            logging.info("Video capture initialized")
            
            while self.is_running:
                if url_refresh_sec and (time.time() - last_url_refresh) >= url_refresh_sec:
                    try:
                        self._release_capture(cap)
                        cap = self._open_video_capture()
                        last_url_refresh = time.time()
                        logging.info("Refreshed YouTube playback URL")
                    except Exception as e:
                        logging.warning(f"URL refresh failed: {e}")
                        self.stream_error = str(e)

                ret, frame = self._read_frame(cap)
                
                if not ret or frame is None:
                    logging.warning("Failed to capture frame, reconnecting...")
                    self.stream_error = "Reconnecting to stream..."
                    time.sleep(2.0)
                    try:
                        self._release_capture(cap)
                        cap = self._open_video_capture()
                        last_url_refresh = time.time()
                    except Exception as e:
                        logging.error(f"Reconnect failed: {e}")
                        self.stream_error = str(e)
                        time.sleep(3.0)
                    continue
                
                current_time = time.time()
                
                if current_time - last_frame_time >= frame_interval:
                    try:
                        frame_data = {
                            'frame': frame.copy(),
                            'timestamp': datetime.now(),
                            'frame_time': current_time
                        }
                        self.frame_queue.put(frame_data, timeout=0.1)
                        last_frame_time = current_time
                        self.stats['last_frame_time'] = current_time
                        self.stats['frames_captured'] += 1
                        if self.stats['frames_captured'] == 1:
                            self.stream_error = None
                            logging.info("First frame queued — queue size %s", self.frame_queue.qsize())
                        elif self.stats['frames_captured'] % 15 == 0:
                            logging.info(
                                "Captured %s frames, queue %s",
                                self.stats['frames_captured'],
                                self.frame_queue.qsize(),
                            )
                    except queue.Full:
                        logging.warning("Frame queue full, dropping frame")
                
                time.sleep(0.02)
                
        except Exception as e:
            logging.error(f"Error in video capture loop: {e}")
            self.stream_error = str(e)
        
        finally:
            self._release_capture(cap)
            logging.info("Video capture loop ended")
    
    def _audio_capture_loop(self):
        """Audio capture loop (placeholder implementation)"""
        # This would typically use ffmpeg or gstreamer to extract audio
        # from the RTSP stream in real-time
        
        chunk_duration = SPEECH_CONFIG['chunk_duration']
        
        while self.is_running:
            try:
                # Extract audio chunk from RTSP (placeholder)
                audio_data = extract_audio_from_rtsp(
                    self.rtsp_url, 
                    duration=chunk_duration
                )
                
                if self.speech_transcriber:
                    self.speech_transcriber.add_audio(audio_data)
                
                # Sleep for chunk duration
                time.sleep(chunk_duration)
                
            except Exception as e:
                logging.error(f"Error in audio capture loop: {e}")
                time.sleep(5.0)
        
        logging.info("Audio capture loop ended")
    
    def _processing_loop(self):
        """Main processing loop for text extraction"""
        
        while self.is_running:
            try:
                if self.utr_predictor is None:
                    time.sleep(0.5)
                    continue

                # Process video frames
                self._process_video_frames()
                
                # Process audio transcriptions
                if self.speech_transcriber:
                    self._process_audio_transcriptions()
                
                # Small sleep to prevent excessive CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Error in processing loop: {e}")
                time.sleep(1.0)
        
        logging.info("Processing loop ended")
    
    def _process_video_frames(self):
        """Process queued video frames for text extraction"""
        frames_to_process = []
        
        # Collect frames for batch processing
        while len(frames_to_process) < PROCESSING_CONFIG['batch_size']:
            try:
                frame_data = self.frame_queue.get(timeout=0.1)
                frames_to_process.append(frame_data)
            except queue.Empty:
                break
        
        if not frames_to_process:
            return
        
        # Process frames
        for frame_data in frames_to_process:
            self._process_single_frame(frame_data)
            self.stats['frames_processed'] += 1
    
    def _process_single_frame(self, frame_data: Dict):
        """Process a single frame for text extraction"""
        frame = frame_data['frame']
        timestamp = frame_data['timestamp']
        
        try:
            # Calculate frame hash to avoid duplicate processing
            frame_hash = self._calculate_frame_hash(frame)
            
            if frame_hash == self.last_frame_hash:
                return  # Skip identical frames
            
            self.last_frame_hash = frame_hash
            
            # Extract text from different regions
            extraction_results = self.utr_predictor.extract_text_regions(
                frame, self._get_text_regions()
            )
            
            # Process each region's results
            for region_name, result in extraction_results.items():
                if result['text'] and result['confidence'] >= PROCESSING_CONFIG['ocr_confidence_threshold']:
                    # Clean extracted text
                    cleaned_text = clean_urdu_text(result['text'])
                    youtube = is_youtube_url(self.source_url)
                    min_len = 10 if youtube else PROCESSING_CONFIG.get('min_urdu_text_length', 6)
                    min_long = 2 if youtube else 1
                    if not is_plausible_urdu_text(
                        cleaned_text, min_length=min_len, min_long_words=min_long
                    ):
                        logging.debug(
                            "Skipped low-quality OCR (%s): %s",
                            region_name,
                            cleaned_text[:40],
                        )
                        continue

                    if cleaned_text and not self._is_duplicate_text(cleaned_text, region_name):
                        # Save screenshot if configured
                        screenshot_path = None
                        if result['priority'] == 'high':
                            screenshot_path = self._save_screenshot(frame, timestamp, region_name)
                        
                        # Store in database
                        extraction_uuid = self.database.insert_text_extraction(
                            region_name=region_name,
                            text=cleaned_text,
                            confidence=result['confidence'],
                            priority=result['priority'],
                            region_coords=result['region'],
                            frame_hash=frame_hash,
                            screenshot_path=str(screenshot_path) if screenshot_path else None,
                            channel_name=self.channel_name
                        )
                        
                        if extraction_uuid:
                            self.stats['text_extractions'] += 1
                            
                            # Check for alerts
                            self._check_text_alerts(extraction_uuid, cleaned_text)
                            
                            # Update text cache
                            self.text_cache[f"{region_name}:{cleaned_text[:50]}"] = time.time()
                            
                            logging.info(f"Extracted text from {region_name}: {cleaned_text[:100]}...")
            
        except Exception as e:
            logging.error(f"Error processing frame: {e}")
    
    def _process_audio_transcriptions(self):
        """Process audio transcription results"""
        if not self.speech_transcriber:
            return
        
        transcriptions = self.speech_transcriber.get_transcriptions()
        
        for transcription in transcriptions:
            try:
                text = transcription['text']
                confidence = transcription['confidence']
                duration = transcription['chunk_duration']
                
                if confidence >= PROCESSING_CONFIG['ocr_confidence_threshold']:
                    # Clean transcribed text
                    cleaned_text = clean_urdu_text(text)
                    
                    if cleaned_text and not self._is_duplicate_text(cleaned_text, 'audio'):
                        # Save audio clip if high priority
                        audio_path = None
                        if any(keyword in cleaned_text.lower() for keyword in ALERTS_CONFIG['keywords']):
                            # Would save audio clip here in production
                            pass
                        
                        # Store in database
                        transcription_uuid = self.database.insert_audio_transcription(
                            text=cleaned_text,
                            confidence=confidence,
                            duration=duration,
                            audio_path=audio_path,
                            channel_name=self.channel_name
                        )
                        
                        if transcription_uuid:
                            self.stats['audio_transcriptions'] += 1
                            
                            # Check for alerts
                            self._check_audio_alerts(transcription_uuid, cleaned_text)
                            
                            # Update text cache
                            self.text_cache[f"audio:{cleaned_text[:50]}"] = time.time()
                            
                            logging.info(f"Transcribed audio: {cleaned_text[:100]}...")
            
            except Exception as e:
                logging.error(f"Error processing audio transcription: {e}")
    
    def _calculate_frame_hash(self, frame: np.ndarray) -> str:
        """Calculate hash of frame for duplicate detection"""
        # Resize frame for faster hashing
        small_frame = cv2.resize(frame, (64, 64))
        gray_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate hash
        frame_bytes = gray_frame.tobytes()
        return hashlib.md5(frame_bytes).hexdigest()
    
    def _is_duplicate_text(self, text: str, region_name: str) -> bool:
        """Check if text is a recent duplicate"""
        cache_key = f"{region_name}:{text[:50]}"
        current_time = time.time()
        
        # Clean old cache entries
        expired_keys = [
            key for key, timestamp in self.text_cache.items()
            if current_time - timestamp > 60  # 1 minute cache
        ]
        for key in expired_keys:
            del self.text_cache[key]
        
        # Check for duplicates
        for cached_key, timestamp in self.text_cache.items():
            if cached_key.startswith(f"{region_name}:"):
                cached_text = cached_key.split(':', 1)[1]
                similarity = calculate_text_similarity(text[:50], cached_text)
                
                if similarity >= PROCESSING_CONFIG['duplicate_text_threshold']:
                    return True
        
        return False
    
    def _save_screenshot(self, frame: np.ndarray, timestamp: datetime, region_name: str) -> Optional[Path]:
        """Save screenshot of frame"""
        try:
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{region_name}_{self.channel_name}.jpg"
            filepath = STORAGE_CONFIG['screenshots_dir'] / filename
            
            # Save image
            cv2.imwrite(str(filepath), frame)
            
            return filepath
            
        except Exception as e:
            logging.error(f"Error saving screenshot: {e}")
            return None
    
    def _check_text_alerts(self, content_id: str, text: str):
        """Check text for alert keywords"""
        if ALERTS_CONFIG['enabled']:
            matched_keywords = self.alert_system.check_keywords(text)
            
            if matched_keywords:
                alert_uuid = self.database.insert_alert(
                    alert_type='keyword_match',
                    content_type='text',
                    content_id=content_id,
                    matched_keywords=matched_keywords,
                    alert_text=text[:500],
                    severity='high' if any(kw in ['عاجل', 'breaking'] for kw in matched_keywords) else 'medium'
                )
                
                if alert_uuid:
                    self.stats['alerts_triggered'] += 1
                    self.alert_system.trigger_notifications(alert_uuid, text, matched_keywords)
    
    def _check_audio_alerts(self, content_id: str, text: str):
        """Check audio transcription for alert keywords"""
        if ALERTS_CONFIG['enabled']:
            matched_keywords = self.alert_system.check_keywords(text)
            
            if matched_keywords:
                alert_uuid = self.database.insert_alert(
                    alert_type='keyword_match',
                    content_type='audio',
                    content_id=content_id,
                    matched_keywords=matched_keywords,
                    alert_text=text[:500],
                    severity='high' if any(kw in ['عاجل', 'breaking'] for kw in matched_keywords) else 'medium'
                )
                
                if alert_uuid:
                    self.stats['alerts_triggered'] += 1
                    self.alert_system.trigger_notifications(alert_uuid, text, matched_keywords)
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics"""
        current_time = datetime.now()
        runtime = (current_time - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0
        
        stats = self.stats.copy()
        stats.update({
            'runtime_seconds': runtime,
            'frames_per_second': self.stats['frames_processed'] / runtime if runtime > 0 else 0,
            'extractions_per_minute': self.stats['text_extractions'] / (runtime / 60) if runtime > 0 else 0,
            'queue_sizes': {
                'frames': self.frame_queue.qsize(),
                'audio': self.audio_queue.qsize() if hasattr(self, 'audio_queue') else 0
            },
            'is_running': self.is_running,
            'channel_name': self.channel_name,
            'source_url': self.source_url,
            'stream_error': self.stream_error,
            'frames_processed': self.stats['frames_processed'],
            'frames_captured': self.stats['frames_captured'],
        })
        
        # Add speech transcription stats if available
        if self.speech_transcriber:
            speech_stats = self.speech_transcriber.get_statistics()
            stats['speech_transcription'] = speech_stats
        
        return stats
    
    def get_recent_extractions(self, limit: int = 50) -> List[Dict]:
        """Get recent text extractions"""
        return self.database.search_text_extractions(
            channel_name=self.channel_name,
            limit=limit
        )
    
    def get_recent_transcriptions(self, limit: int = 20) -> List[Dict]:
        """Get recent audio transcriptions"""
        return self.database.search_audio_transcriptions(
            channel_name=self.channel_name,
            limit=limit
        )


# Utility functions for integration
def create_news_monitor(rtsp_url: str, channel_name: str = "news_channel") -> NewsMonitor:
    """Create and return a configured news monitor instance"""
    return NewsMonitor(rtsp_url=rtsp_url, channel_name=channel_name)

class MultiChannelNewsMonitor:
    """
    Multi-channel news monitoring system
    Manages multiple NewsMonitor instances for different RTSP channels
    """

    def __init__(self, channel_configs: Dict = None):
        self.channel_configs = channel_configs or RTSP_CHANNELS
        self.monitors = {}
        self.is_running = False
        self.database = NewsDatabase()
        self.alert_system = AlertSystem(self.database)

        # Initialize monitors for enabled channels
        self._initialize_monitors()

        logging.info(f"Multi-channel monitor initialized with {len(self.monitors)} channels")

    def _initialize_monitors(self):
        """Initialize individual monitors for each enabled channel"""
        for channel_id, config in self.channel_configs.items():
            if config.get('enabled', False):
                try:
                    monitor = NewsMonitor(
                        rtsp_url=config['rtsp_url'],
                        channel_name=config['name']
                    )
                    self.monitors[channel_id] = monitor
                    logging.info(f"Initialized monitor for channel: {config['name']}")
                except Exception as e:
                    logging.error(f"Failed to initialize monitor for {config['name']}: {e}")

    def start_monitoring(self):
        """Start monitoring all enabled channels"""
        if self.is_running:
            logging.warning("Multi-channel monitoring is already running")
            return

        try:
            self.is_running = True

            # Start all monitors
            for channel_id, monitor in self.monitors.items():
                try:
                    monitor.start_monitoring()
                    logging.info(f"Started monitoring for channel: {monitor.channel_name}")
                except Exception as e:
                    logging.error(f"Failed to start monitor for {channel_id}: {e}")

            logging.info(f"Multi-channel monitoring started for {len(self.monitors)} channels")

        except Exception as e:
            logging.error(f"Failed to start multi-channel monitoring: {e}")
            self.stop_monitoring()
            raise

    def stop_monitoring(self):
        """Stop monitoring all channels"""
        if not self.is_running:
            return

        logging.info("Stopping multi-channel monitoring...")

        self.is_running = False

        # Stop all monitors
        for channel_id, monitor in self.monitors.items():
            try:
                monitor.stop_monitoring()
                logging.info(f"Stopped monitoring for channel: {monitor.channel_name}")
            except Exception as e:
                logging.error(f"Error stopping monitor for {channel_id}: {e}")

        logging.info("Multi-channel monitoring stopped")

    def get_statistics(self) -> Dict:
        """Get combined statistics for all channels"""
        total_stats = {
            'frames_processed': 0,
            'text_extractions': 0,
            'audio_transcriptions': 0,
            'alerts_triggered': 0,
            'channels_running': 0,
            'channels_total': len(self.monitors),
            'start_time': None,
            'channel_stats': {}
        }

        for channel_id, monitor in self.monitors.items():
            try:
                channel_stats = monitor.get_statistics()
                total_stats['channel_stats'][channel_id] = channel_stats

                # Sum up totals
                total_stats['frames_processed'] += channel_stats.get('frames_processed', 0)
                total_stats['text_extractions'] += channel_stats.get('text_extractions', 0)
                total_stats['audio_transcriptions'] += channel_stats.get('audio_transcriptions', 0)
                total_stats['alerts_triggered'] += channel_stats.get('alerts_triggered', 0)

                if channel_stats.get('is_running', False):
                    total_stats['channels_running'] += 1

                # Track earliest start time
                if channel_stats.get('start_time') and not total_stats['start_time']:
                    total_stats['start_time'] = channel_stats['start_time']
                elif (channel_stats.get('start_time') and total_stats['start_time'] and
                      channel_stats['start_time'] < total_stats['start_time']):
                    total_stats['start_time'] = channel_stats['start_time']

            except Exception as e:
                logging.error(f"Error getting statistics for {channel_id}: {e}")

        # Calculate runtime
        if total_stats['start_time']:
            from datetime import datetime
            runtime = (datetime.now() - total_stats['start_time']).total_seconds()
            total_stats['runtime_seconds'] = runtime
        else:
            total_stats['runtime_seconds'] = 0

        return total_stats

    def get_channel_status(self) -> Dict:
        """Get status of all channels"""
        status = {
            'overall_running': self.is_running,
            'channels': {}
        }

        for channel_id, monitor in self.monitors.items():
            try:
                channel_stats = monitor.get_statistics()
                status['channels'][channel_id] = {
                    'name': monitor.channel_name,
                    'running': channel_stats.get('is_running', False),
                    'frames_processed': channel_stats.get('frames_processed', 0),
                    'text_extractions': channel_stats.get('text_extractions', 0),
                    'audio_transcriptions': channel_stats.get('audio_transcriptions', 0),
                    'alerts_triggered': channel_stats.get('alerts_triggered', 0)
                }
            except Exception as e:
                status['channels'][channel_id] = {
                    'name': monitor.channel_name,
                    'running': False,
                    'error': str(e)
                }

        return status

    def add_channel(self, channel_id: str, config: Dict):
        """Add a new channel to monitoring"""
        try:
            if channel_id in self.monitors:
                logging.warning(f"Channel {channel_id} already exists")
                return False

            monitor = NewsMonitor(
                rtsp_url=config['rtsp_url'],
                channel_name=config['name']
            )

            self.monitors[channel_id] = monitor
            self.channel_configs[channel_id] = config

            logging.info(f"Added new channel: {config['name']}")

            # Start monitoring if overall system is running
            if self.is_running:
                monitor.start_monitoring()
                logging.info(f"Started monitoring for new channel: {config['name']}")

            return True

        except Exception as e:
            logging.error(f"Failed to add channel {channel_id}: {e}")
            return False

    def remove_channel(self, channel_id: str):
        """Remove a channel from monitoring"""
        try:
            if channel_id not in self.monitors:
                logging.warning(f"Channel {channel_id} not found")
                return False

            # Stop the monitor if it's running
            if self.monitors[channel_id].is_running:
                self.monitors[channel_id].stop_monitoring()

            # Remove from monitors dict
            del self.monitors[channel_id]

            # Remove from config if present
            if channel_id in self.channel_configs:
                del self.channel_configs[channel_id]

            logging.info(f"Removed channel: {channel_id}")
            return True

        except Exception as e:
            logging.error(f"Failed to remove channel {channel_id}: {e}")
            return False

    def get_recent_extractions(self, limit: int = 50) -> List[Dict]:
        """Get recent text extractions from all channels"""
        all_extractions = []

        for monitor in self.monitors.values():
            try:
                extractions = monitor.get_recent_extractions(limit=limit//len(self.monitors))
                all_extractions.extend(extractions)
            except Exception as e:
                logging.error(f"Error getting extractions for {monitor.channel_name}: {e}")

        # Sort by timestamp (most recent first) and limit results
        all_extractions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return all_extractions[:limit]

    def get_recent_transcriptions(self, limit: int = 20) -> List[Dict]:
        """Get recent audio transcriptions from all channels"""
        all_transcriptions = []

        for monitor in self.monitors.values():
            try:
                transcriptions = monitor.get_recent_transcriptions(limit=limit//len(self.monitors))
                all_transcriptions.extend(transcriptions)
            except Exception as e:
                logging.error(f"Error getting transcriptions for {monitor.channel_name}: {e}")

        # Sort by timestamp (most recent first) and limit results
        all_transcriptions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return all_transcriptions[:limit]


def monitor_multiple_channels(channel_configs: List[Dict]) -> Dict[str, NewsMonitor]:
    """Create monitors for multiple channels (legacy function)"""
    monitors = {}

    for config in channel_configs:
        channel_name = config['name']
        rtsp_url = config['rtsp_url']

        monitor = NewsMonitor(rtsp_url=rtsp_url, channel_name=channel_name)
        monitors[channel_name] = monitor

        logging.info(f"Created monitor for channel: {channel_name}")

    return monitors