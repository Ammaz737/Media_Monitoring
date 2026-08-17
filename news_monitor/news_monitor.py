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
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

from config import (
    RTSP_CHANNELS, RTSP_URL, TEXT_REGIONS, YOUTUBE_TEXT_REGIONS,
    PROCESSING_CONFIG, STORAGE_CONFIG, ALERTS_CONFIG, SPEECH_CONFIG,
    OLLAMA_OCR_CONFIG, ROBOFLOW_CONFIG, YOLO_TICKER_CONFIG,
    normalize_text_regions,
)
from utrnet_wrapper import (
    UTRNetPredictor,
    SharedOcrService,
    clean_urdu_text,
    calculate_text_similarity,
    is_plausible_urdu_text,
)
from ollama_ocr import OllamaVisionOcr, SharedOllamaOcrService
from speech_transcription import (
    RealtimeSpeechTranscriber,
    SharedSpeechService,
    extract_audio_from_rtsp,
    save_audio_chunk,
)
from database import NewsDatabase
from alert_system import AlertSystem
from stream_resolver import (
    resolve_stream_url,
    is_youtube_url,
    is_audio_stream_url,
    ffmpeg_available,
    FfmpegFrameReader,
    redact_stream_url,
    stream_url_kind,
)

class NewsMonitor:
    """
    Main news monitoring system
    Processes RTSP streams for real-time text and audio extraction
    """
    
    def __init__(
        self,
        rtsp_url: str = None,
        channel_name: str = "news_channel",
        speech_enabled: bool = True,
        text_regions: Dict = None,
        shared_ocr: Optional[SharedOcrService] = None,
        shared_ollama: Optional[SharedOllamaOcrService] = None,
        shared_speech: Optional[SharedSpeechService] = None,
    ):
        self.source_url = (rtsp_url or RTSP_URL).strip()
        self.rtsp_url = self.source_url
        self.channel_name = channel_name
        self.speech_enabled = speech_enabled
        self.stream_error: Optional[str] = None
        self.custom_text_regions = text_regions if isinstance(text_regions, dict) else None
        self.shared_ocr = shared_ocr
        self.shared_ollama = shared_ollama
        self.shared_speech = shared_speech
        self._owns_utr_predictor = shared_ocr is None
        self.audio_only = is_audio_stream_url(self.source_url)

        self.utr_predictor = None
        self.ollama_ocr: Optional[OllamaVisionOcr] = None
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

        # Latest frame for OCR region editor (YouTube/RTSP preview)
        self._preview_lock = threading.Lock()
        self._latest_preview_frame: Optional[np.ndarray] = None
        
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
        # Soft fingerprints of ticker/headline crops (region_name -> float32 array)
        self.last_crop_fp: Dict[str, np.ndarray] = {}
        self.last_crop_ocr_time: Dict[str, float] = {}
        self._roboflow_box: Optional[Tuple] = None  # (cls, x1, y1, x2, y2) pixels
        
        # Setup directories
        self._setup_directories()
        
        logging.info(f"News monitor initialized for {self.source_url}")
    
    def _setup_directories(self):
        """Create necessary directories"""
        STORAGE_CONFIG['screenshots_dir'].mkdir(parents=True, exist_ok=True)
        STORAGE_CONFIG['audio_clips_dir'].mkdir(parents=True, exist_ok=True)
        (STORAGE_CONFIG['audio_clips_dir'] / 'transcriptions').mkdir(parents=True, exist_ok=True)
        (STORAGE_CONFIG['audio_clips_dir'] / 'clips').mkdir(parents=True, exist_ok=True)
        STORAGE_CONFIG['ocr_crops_dir'].mkdir(parents=True, exist_ok=True)
        STORAGE_CONFIG['ollama_rejected_dir'].mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent / 'logs').mkdir(parents=True, exist_ok=True)
        (Path(__file__).parent / 'data').mkdir(parents=True, exist_ok=True)
    
    def initialize_models(self, load_speech: bool = None):
        """Initialize OCR (required). Speech is optional and can be deferred."""
        if load_speech is None:
            load_speech = self.speech_enabled
        try:
            if self.utr_predictor is None:
                if self.shared_ocr is not None:
                    self.utr_predictor = self.shared_ocr.ensure_loaded()
                    logging.info("Attached shared UTRNet for %s", self.channel_name)
                else:
                    logging.info(
                        "Loading standalone UTRNet for %s (single-channel mode, not shared)",
                        self.channel_name,
                    )
                    self.utr_predictor = UTRNetPredictor(
                        device="cuda",
                        batch_size=PROCESSING_CONFIG["batch_size"],
                    )
                    logging.info(
                        "Standalone UTRNet loaded for %s",
                        self.channel_name,
                    )

            if self.ollama_ocr is None and OLLAMA_OCR_CONFIG.get("enabled", True):
                if self.shared_ollama is not None:
                    self.ollama_ocr = self.shared_ollama.ensure_loaded()
                    logging.info("Attached shared Ollama OCR for %s", self.channel_name)
                else:
                    self.ollama_ocr = OllamaVisionOcr()
                    logging.info(
                        "Standalone Ollama OCR ready for %s (model=%s)",
                        self.channel_name,
                        OLLAMA_OCR_CONFIG.get("model"),
                    )

            if load_speech:
                self._init_speech()

        except Exception as e:
            logging.error(f"Failed to initialize models: {e}")
            raise

    def _init_speech(self) -> bool:
        """Load Whisper for this channel. Returns True on success."""
        if self.speech_transcriber is not None:
            return True
        if not SPEECH_CONFIG.get('enabled', True):
            return False
        try:
            from speech_transcription import WHISPER_AVAILABLE
            if not WHISPER_AVAILABLE:
                logging.info("Speech transcription disabled - Whisper not available")
                return False
            logging.info("Loading Whisper model for %s…", self.channel_name)
            model = self.shared_speech.ensure_loaded() if self.shared_speech else None
            self.speech_transcriber = RealtimeSpeechTranscriber(transcriber=model)
            self.speech_transcriber.start()
            logging.info("Speech transcription initialized for %s", self.channel_name)
            return True
        except Exception as e:
            logging.warning(f"Speech transcription disabled: {e}")
            self.speech_transcriber = None
            return False

    def start_speech_transcription(self) -> bool:
        """Start audio capture after OCR is already running (deferred boot)."""
        if not self.is_running:
            return False
        if self.audio_thread and self.audio_thread.is_alive():
            return True
        if not self._init_speech():
            return False
        self.audio_thread = threading.Thread(
            target=self._audio_capture_loop, daemon=True, name=f"audio-{self.channel_name}"
        )
        self.audio_thread.start()
        logging.info("Audio transcription thread started for %s", self.channel_name)
        return True
    
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
            self.last_crop_fp.clear()
            self.last_crop_ocr_time.clear()
            self._roboflow_box = None
            self._clear_queues()

            self.is_running = True
            self.stats['start_time'] = datetime.now()

            if self.audio_only:
                self.stream_error = "Starting audio capture…"
                logging.info("Audio-only channel %s — skipping video/OCR", self.channel_name)

                def _boot_audio():
                    try:
                        self.processing_thread = threading.Thread(
                            target=self._processing_loop, daemon=True, name="audio-processing"
                        )
                        self.processing_thread.start()
                        if self.speech_enabled:
                            self.start_speech_transcription()
                        self.stream_error = None
                        logging.info("Audio processing started for %s", self.channel_name)
                    except Exception as e:
                        logging.error("Failed to start audio processing: %s", e)
                        self.stream_error = str(e)

                threading.Thread(
                    target=_boot_audio, daemon=True, name="audio-boot"
                ).start()
                logging.info("News monitoring started (audio-only)")
                return

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
                    # Load OCR first; speech after (or deferred by MultiChannel)
                    self.initialize_models(load_speech=False)
                    self.processing_thread = threading.Thread(
                        target=self._processing_loop, daemon=True, name="frame-processing"
                    )
                    self.processing_thread.start()

                    if self.speech_enabled:
                        self.start_speech_transcription()

                    if self.stats['frames_captured'] > 0:
                        self.stream_error = None
                    else:
                        self.stream_error = "OCR ready — waiting for video frames…"
                    logging.info("OCR processing thread started for %s", self.channel_name)
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
        
        # Clean up models (shared OCR is owned by MultiChannelNewsMonitor)
        if self._owns_utr_predictor and self.utr_predictor:
            self.utr_predictor.cleanup()
        self.utr_predictor = None
        
        if self.speech_transcriber:
            self.speech_transcriber.cleanup()
            self.speech_transcriber = None
        
        # Clear queues
        self._clear_queues()

        with self._preview_lock:
            self._latest_preview_frame = None
        
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
        """Prefer per-channel boxes; else YouTube strips or global RTSP layout."""
        if self.custom_text_regions:
            fallback = (
                YOUTUBE_TEXT_REGIONS
                if is_youtube_url(self.source_url)
                else TEXT_REGIONS
            )
            return normalize_text_regions(self.custom_text_regions, fallback)
        if is_youtube_url(self.source_url):
            return YOUTUBE_TEXT_REGIONS
        return TEXT_REGIONS

    def _use_roboflow_ticker(self) -> bool:
        return bool(ROBOFLOW_CONFIG.get("enabled")) and not is_youtube_url(self.source_url)

    def _use_yolo_ticker(self) -> bool:
        return bool(YOLO_TICKER_CONFIG.get("enabled")) and not is_youtube_url(self.source_url)

    def set_text_regions(self, regions: Optional[Dict]) -> None:
        """Hot-update OCR crop boxes for this channel (Settings editor)."""
        self.custom_text_regions = regions if isinstance(regions, dict) else None

    def get_preview_frame(self) -> Optional[np.ndarray]:
        """Copy of the most recent captured frame (for region-editor snapshots)."""
        with self._preview_lock:
            if self._latest_preview_frame is None:
                return None
            return self._latest_preview_frame.copy()

    def clear_queues(self) -> Dict[str, int]:
        """Drop all queued frames/audio. Returns counts removed."""
        dropped_frames = 0
        dropped_audio = 0
        while True:
            try:
                self.frame_queue.get_nowait()
                dropped_frames += 1
            except queue.Empty:
                break
        while True:
            try:
                self.audio_queue.get_nowait()
                dropped_audio += 1
            except queue.Empty:
                break
        if dropped_frames or dropped_audio:
            logging.info(
                "Cleared queues on %s (frames=%s, audio=%s)",
                self.channel_name,
                dropped_frames,
                dropped_audio,
            )
        return {"frames": dropped_frames, "audio": dropped_audio}

    def _clear_queues(self):
        """Clear processing queues"""
        self.clear_queues()
    
    def _wait_reconnect(self, seconds: float = 120.0) -> None:
        """Sleep up to `seconds` while still running (interruptible)."""
        deadline = time.time() + seconds
        while self.is_running and time.time() < deadline:
            time.sleep(min(1.0, max(0.0, deadline - time.time())))

    def _video_capture_loop(self):
        """Main video capture loop — retries RTSP every 2 minutes on failure."""
        RECONNECT_INTERVAL_SEC = 120.0
        cap = None
        last_frame_time = 0
        last_url_refresh = time.time()
        frame_interval = PROCESSING_CONFIG['frame_interval']
        url_refresh_sec = 75 if is_youtube_url(self.source_url) else 0

        while self.is_running:
            try:
                if cap is None:
                    self.stream_error = "Connecting to stream…"
                    logging.info("Opening video capture for %s", self.channel_name)
                    cap = self._open_video_capture()
                    last_url_refresh = time.time()
                    logging.info("Video capture initialized for %s", self.channel_name)
                    if self.stats['frames_captured'] == 0:
                        self.stream_error = "Connected — waiting for frames…"
                    else:
                        self.stream_error = None

                if url_refresh_sec and (time.time() - last_url_refresh) >= url_refresh_sec:
                    try:
                        self._release_capture(cap)
                        cap = self._open_video_capture()
                        last_url_refresh = time.time()
                        logging.info("Refreshed YouTube playback URL")
                    except Exception as e:
                        logging.warning(f"URL refresh failed: {e}")
                        self.stream_error = str(e)
                        self._release_capture(cap)
                        cap = None
                        logging.warning(
                            "Will retry %s in %ss…",
                            self.channel_name,
                            int(RECONNECT_INTERVAL_SEC),
                        )
                        self._wait_reconnect(RECONNECT_INTERVAL_SEC)
                        continue

                ret, frame = self._read_frame(cap)

                if not ret or frame is None:
                    logging.warning(
                        "Failed to capture frame on %s, reconnecting...",
                        self.channel_name,
                    )
                    self.stream_error = "Reconnecting to stream…"
                    time.sleep(2.0)
                    try:
                        self._release_capture(cap)
                        cap = self._open_video_capture()
                        last_url_refresh = time.time()
                    except Exception as e:
                        logging.error(f"Reconnect failed for {self.channel_name}: {e}")
                        self.stream_error = str(e)
                        self._release_capture(cap)
                        cap = None
                        logging.warning(
                            "Will retry %s in %ss…",
                            self.channel_name,
                            int(RECONNECT_INTERVAL_SEC),
                        )
                        self._wait_reconnect(RECONNECT_INTERVAL_SEC)
                    continue

                current_time = time.time()

                if current_time - last_frame_time >= frame_interval:
                    try:
                        preview = frame.copy()
                        with self._preview_lock:
                            self._latest_preview_frame = preview
                        frame_data = {
                            'frame': preview,
                            'timestamp': datetime.now(),
                            'frame_time': current_time
                        }
                        # Keep queue near-live: drop backlog before enqueue
                        while self.frame_queue.qsize() > 0:
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                break
                        self.frame_queue.put(frame_data, timeout=0.1)
                        last_frame_time = current_time
                        self.stats['last_frame_time'] = current_time
                        self.stats['frames_captured'] += 1
                        if self.stats['frames_captured'] == 1:
                            self.stream_error = None
                            logging.info(
                                "First frame queued on %s — queue size %s",
                                self.channel_name,
                                self.frame_queue.qsize(),
                            )
                        elif self.stats['frames_captured'] % 15 == 0:
                            logging.info(
                                "Captured %s frames on %s, queue %s",
                                self.stats['frames_captured'],
                                self.channel_name,
                                self.frame_queue.qsize(),
                            )
                    except queue.Full:
                        logging.warning("Frame queue full, dropping frame")

                time.sleep(0.02)

            except Exception as e:
                logging.error(f"Error in video capture loop ({self.channel_name}): {e}")
                self.stream_error = str(e)
                self._release_capture(cap)
                cap = None
                if not self.is_running:
                    break
                logging.warning(
                    "Will retry %s in %ss…",
                    self.channel_name,
                    int(RECONNECT_INTERVAL_SEC),
                )
                self._wait_reconnect(RECONNECT_INTERVAL_SEC)

        self._release_capture(cap)
        logging.info("Video capture loop ended for %s", self.channel_name)
    
    def _audio_capture_loop(self):
        """Audio capture loop for RTSP / HLS / YouTube streams"""
        chunk_duration = SPEECH_CONFIG['chunk_duration']
        consecutive_failures = 0
        logging.info(
            "Audio capture loop started for %s (chunk=%ss)",
            self.channel_name,
            chunk_duration,
        )

        while self.is_running:
            try:
                # Keep YouTube/HLS playback URL fresh (same as video path)
                stream_url = (
                    self._refresh_playback_url()
                    if is_youtube_url(self.source_url)
                    else self.rtsp_url
                )
                logging.debug(
                    "Audio pull target for %s: %s (%s)",
                    self.channel_name,
                    redact_stream_url(stream_url)[:160],
                    stream_url_kind(stream_url),
                )

                audio_data = extract_audio_from_rtsp(
                    stream_url,
                    duration=chunk_duration,
                    label=self.channel_name,
                )

                # Skip failed / empty / near-silence pulls (don't feed Whisper)
                if audio_data is None or len(audio_data) == 0:
                    consecutive_failures += 1
                    backoff = min(30.0, 2.0 * consecutive_failures)
                    if consecutive_failures <= 3 or consecutive_failures % 5 == 0:
                        logging.warning(
                            "Audio pull failed on %s (attempt %s) — retry in %.0fs",
                            self.channel_name,
                            consecutive_failures,
                            backoff,
                        )
                    time.sleep(backoff)
                    continue

                peak = float(np.max(np.abs(audio_data))) if len(audio_data) else 0.0
                if peak < 1e-4:
                    consecutive_failures += 1
                    if consecutive_failures <= 3 or consecutive_failures % 5 == 0:
                        logging.warning(
                            "Audio pull near-silence on %s (peak=%.2e) — skipping Whisper",
                            self.channel_name,
                            peak,
                        )
                    time.sleep(min(15.0, 2.0 * consecutive_failures))
                    continue

                consecutive_failures = 0
                if self.speech_transcriber:
                    actual_sec = len(audio_data) / SPEECH_CONFIG['sample_rate']
                    capture_start = datetime.now() - timedelta(seconds=actual_sec)
                    logging.debug(
                        "Queued %.2fs audio for transcription on %s (start %s)",
                        actual_sec,
                        self.channel_name,
                        capture_start.isoformat(timespec='seconds'),
                    )
                    self.speech_transcriber.add_audio(
                        audio_data, wall_start=capture_start
                    )
                
            except Exception as e:
                logging.error(f"Error in audio capture loop: {e}")
                time.sleep(5.0)
        
        logging.info("Audio capture loop ended")
    
    def _processing_loop(self):
        """Main processing loop for text extraction"""
        
        while self.is_running:
            try:
                if self.audio_only:
                    if self.speech_transcriber:
                        self._process_audio_transcriptions()
                    time.sleep(0.1)
                    continue

                if self.utr_predictor is None:
                    time.sleep(0.5)
                    continue

                # Process frames for region OCR
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

    def _apply_region_extraction(
        self,
        region_name: str,
        result: Dict,
        timestamp: datetime,
        frame_hash: str,
        ocr_crop: Optional[np.ndarray] = None,
        full_frame: Optional[np.ndarray] = None,
        source_label: str = "frame",
    ) -> None:
        """Store OCR result, alerts, and cache updates for one region.

        ocr_crop: region pixels for Ollama refine / rejected debug (crops live in ocr_crops/).
        full_frame: entire captured frame saved to screenshots/ for the UI.
        """
        raw_text = (result.get("text") or "").strip()
        utr_conf = float(result.get("confidence") or 0.0)
        ollama = self.ollama_ocr

        # Low UTRNet confidence → discard (do not call Ollama)
        if ollama is not None and ollama.utrnet_is_low(utr_conf):
            return
        if ollama is None and (
            not raw_text or utr_conf < PROCESSING_CONFIG["ocr_confidence_threshold"]
        ):
            return

        text = raw_text
        confidence = utr_conf
        source = "utrnet"

        # Mid band, or high-conf text with digits → Ollama refine; only keep high-conf replies
        if ollama is not None and ollama.utrnet_needs_ollama(utr_conf, raw_text):
            if ocr_crop is None or getattr(ocr_crop, "size", 0) == 0:
                logging.info(
                    "Ollama skip (%s/%s): utr=%.3f but no crop image",
                    source_label,
                    region_name,
                    utr_conf,
                )
                return

            # Fast gate: if UTRNet draft text is clearly implausible, skip Ollama.
            # This avoids ~1.5–2s/call latency for crops that are likely garbage.
            cleaned_draft = clean_urdu_text(raw_text)
            youtube = is_youtube_url(self.source_url)
            min_len = 10 if youtube else PROCESSING_CONFIG.get("min_urdu_text_length", 6)
            min_long = 2 if youtube else 1
            if not is_plausible_urdu_text(
                cleaned_draft, min_length=min_len, min_long_words=min_long
            ):
                logging.info(
                    "Skipping Ollama refine: implausible UTRNet draft (%s/%s utr=%.2f): %s",
                    source_label,
                    region_name,
                    utr_conf,
                    (cleaned_draft or "").strip()[:60],
                )
                return
            logging.info(
                "Ollama refine start (%s/%s %s): utr=%.3f draft=%s…",
                source_label,
                region_name,
                "digits" if ollama.utrnet_is_high(utr_conf) else "mid-conf",
                utr_conf,
                raw_text[:40],
            )
            ollama_text, ollama_conf = ollama.refine(
                ocr_crop,
                draft_text=raw_text,
                draft_confidence=utr_conf,
            )
            save_min = ollama.save_min_confidence()
            if not ollama_text or ollama_conf < save_min:
                logging.info(
                    "Discarded mid-conf OCR after Ollama (%s/%s utr=%.2f ollama=%.2f): %s",
                    source_label,
                    region_name,
                    utr_conf,
                    ollama_conf,
                    (ollama_text or raw_text)[:60],
                )
                self._save_ollama_rejected(
                    ocr_crop,
                    timestamp=timestamp,
                    region_name=region_name,
                    utr_conf=utr_conf,
                    ollama_conf=ollama_conf,
                    draft_text=raw_text,
                    ollama_text=ollama_text or "",
                    save_min=save_min,
                )
                return
            text = ollama_text
            confidence = ollama_conf
            source = "ollama"
        elif ollama is not None and ollama.utrnet_is_high(utr_conf):
            if not raw_text:
                return
            # High-confidence UTRNet still must clear the app floor
            if confidence < PROCESSING_CONFIG["ocr_confidence_threshold"]:
                return
        elif ollama is None:
            pass
        else:
            # Outside expected bands with ollama enabled
            return

        cleaned_text = clean_urdu_text(text)
        youtube = is_youtube_url(self.source_url)
        min_len = 10 if youtube else PROCESSING_CONFIG.get("min_urdu_text_length", 6)
        min_long = 2 if youtube else 1
        if not is_plausible_urdu_text(cleaned_text, min_length=min_len, min_long_words=min_long):
            logging.info(
                "Skipped low-quality OCR (%s/%s/%s): %s",
                source_label,
                region_name,
                source,
                cleaned_text[:60],
            )
            return

        if not cleaned_text or self._is_duplicate_text(cleaned_text, region_name):
            return

        # Final app gate: discard low confidences
        if confidence < PROCESSING_CONFIG["ocr_confidence_threshold"]:
            return

        # Full frame → screenshots/ for every region (ticker, side_text, …)
        screenshot_path = None
        if full_frame is not None:
            screenshot_path = self._save_screenshot(
                full_frame,
                timestamp,
                region_name,
                box=result.get("region"),
                det_conf=result.get("det_conf"),
            )

        extraction_uuid = self.database.insert_text_extraction(
            region_name=region_name,
            text=cleaned_text,
            confidence=confidence,
            priority=result["priority"],
            region_coords=result["region"],
            frame_hash=frame_hash,
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            channel_name=self.channel_name,
            ocr_engine=source,
        )

        if extraction_uuid:
            self.stats["text_extractions"] += 1
            self._check_text_alerts(extraction_uuid, cleaned_text)
            self.text_cache[f"{region_name}:{cleaned_text[:50]}"] = time.time()
            logging.info(
                "Extracted text from %s (%s/%s conf=%.2f): %s…",
                region_name,
                source_label,
                source,
                confidence,
                cleaned_text[:100],
            )
    
    def _process_video_frames(self):
        """Process queued video frames for text extraction (~1 every frame_interval)."""
        # Keep cadence close to capture interval; avoid bursting a backlog of 4 at once
        max_frames = max(1, int(PROCESSING_CONFIG.get("ocr_frames_per_tick", 1)))
        frames_to_process = []

        while len(frames_to_process) < max_frames:
            try:
                frame_data = self.frame_queue.get(timeout=0.1)
                frames_to_process.append(frame_data)
            except queue.Empty:
                break

        if not frames_to_process:
            return

        # Drop stale backlog so OCR stays near live (~1s), not minutes behind
        dropped = 0
        while self.frame_queue.qsize() > 1:
            try:
                self.frame_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            logging.debug(
                "Dropped %s stale queued frames on %s to keep 1s OCR live",
                dropped,
                self.channel_name,
            )

        for frame_data in frames_to_process:
            self._process_single_frame(frame_data)
            self.stats['frames_processed'] += 1
    
    def _process_single_frame(self, frame_data: Dict):
        """Process a single frame for region text extraction."""
        frame = frame_data['frame']
        timestamp = frame_data['timestamp']
        
        try:
            regions = None
            # YOLO local .pt takes precedence when enabled; Roboflow unchanged otherwise.
            if self._use_yolo_ticker():
                from yolo_ticker import regions_from_detection

                regions, self._roboflow_box = regions_from_detection(
                    frame, self.channel_name, self._roboflow_box
                )
            elif self._use_roboflow_ticker():
                from roboflow_ticker import regions_from_detection

                regions, self._roboflow_box = regions_from_detection(
                    frame, self.channel_name, self._roboflow_box
                )
            # else:
            #     regions = self._get_text_regions()
            if not regions:
                return

            # Pixel dedup before UTRNet (unchanged gate from script.py thresholds)
            changed_regions = self._filter_changed_regions(frame, regions)
            if not changed_regions:
                return

            frame_hash = self._calculate_frame_hash(frame)
            self.last_frame_hash = frame_hash

            extraction_results = self.utr_predictor.extract_text_regions(
                frame,
                changed_regions,
                channel_name=self.channel_name,
            )
            
            for region_name, result in extraction_results.items():
                # Crop for Ollama / debug only — full frame goes to screenshots/
                ocr_crop = result.get("ocr_image")
                if ocr_crop is None or getattr(ocr_crop, "size", 0) == 0:
                    coords = result.get("region")
                    if coords and len(coords) == 4:
                        x1, y1, x2, y2 = [int(v) for v in coords]
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            ocr_crop = crop
                self._apply_region_extraction(
                    region_name=region_name,
                    result=result,
                    timestamp=timestamp,
                    frame_hash=frame_hash,
                    ocr_crop=ocr_crop,
                    full_frame=frame,
                    source_label="frame",
                )
            
        except Exception as e:
            logging.error(f"Error processing frame: {e}")

    def _crop_fingerprint(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Compact grayscale fingerprint for soft ticker change detection.
        Downscale + optional blur so YouTube/RTSP compression flicker is ignored.
        """
        if crop is None or getattr(crop, "size", 0) == 0:
            return None
        tw = max(8, int(PROCESSING_CONFIG.get("crop_change_width", 160)))
        th = max(8, int(PROCESSING_CONFIG.get("crop_change_height", 32)))
        small = cv2.resize(crop, (tw, th), interpolation=cv2.INTER_AREA)
        if len(small.shape) == 3:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        else:
            gray = small
        blur_k = int(PROCESSING_CONFIG.get("crop_change_blur", 3) or 0)
        if blur_k >= 3:
            if blur_k % 2 == 0:
                blur_k += 1
            gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
        return gray.astype(np.float32)

    def _crop_mean_diff(self, a: np.ndarray, b: np.ndarray) -> float:
        """Mean absolute pixel difference (0–255 scale)."""
        if a is None or b is None or a.shape != b.shape:
            return 255.0
        return float(np.mean(np.abs(a - b)))

    def _filter_changed_regions(self, frame: np.ndarray, regions: Dict) -> Dict:
        """
        Keep only regions whose ticker/headline crop changed enough to OCR.
        Uses mean abs diff on a blurred downscale — better than exact MD5 for
        live YouTube and RTSP news streams.
        """
        if not PROCESSING_CONFIG.get("crop_change_enabled", True):
            return dict(regions)

        h, w = frame.shape[:2]
        min_h = int(PROCESSING_CONFIG.get("min_region_height_px", 22))
        min_w = int(PROCESSING_CONFIG.get("min_region_width_px", 80))
        threshold = float(PROCESSING_CONFIG.get("crop_change_mean_diff", 10.0))
        force_sec = float(PROCESSING_CONFIG.get("crop_change_force_ocr_sec", 30.0) or 0.0)
        now = time.time()
        changed: Dict = {}

        for region_name, region_config in regions.items():
            try:
                x1, y1, x2, y2 = region_config["region"]
                x1, y1, x2, y2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
                crop = frame[y1:y2, x1:x2]
                if (
                    crop.size == 0
                    or crop.shape[0] < min_h
                    or crop.shape[1] < min_w
                ):
                    continue

                fp = self._crop_fingerprint(crop)
                if fp is None:
                    continue

                prev = self.last_crop_fp.get(region_name)
                last_ocr = self.last_crop_ocr_time.get(region_name, 0.0)
                force = (
                    force_sec > 0
                    and prev is not None
                    and (now - last_ocr) >= force_sec
                )
                diff = (
                    self._crop_mean_diff(prev, fp) if prev is not None else 255.0
                )

                if prev is not None and not force and diff < threshold:
                    continue

                self.last_crop_fp[region_name] = fp
                self.last_crop_ocr_time[region_name] = now
                changed[region_name] = region_config
                if force and diff < threshold:
                    logging.debug(
                        "Force OCR %s/%s after %.0fs (diff=%.1f < thr=%.1f)",
                        self.channel_name,
                        region_name,
                        now - last_ocr,
                        diff,
                        threshold,
                    )
                elif prev is not None:
                    logging.debug(
                        "Crop changed %s/%s mean_diff=%.1f",
                        self.channel_name,
                        region_name,
                        diff,
                    )
            except Exception as e:
                logging.warning(
                    "Crop-change check failed for %s/%s: %s — OCR anyway",
                    self.channel_name,
                    region_name,
                    e,
                )
                changed[region_name] = region_config

        return changed
    
    def _save_transcription_audio(
        self, audio_data: np.ndarray, record_uuid: str
    ) -> Optional[Path]:
        """Persist the WAV chunk that produced a transcription."""
        if audio_data is None or len(audio_data) == 0:
            return None
        try:
            clips_dir = STORAGE_CONFIG['audio_clips_dir'] / 'transcriptions'
            clips_dir.mkdir(parents=True, exist_ok=True)
            filepath = clips_dir / f'{record_uuid}.wav'
            if save_audio_chunk(
                audio_data,
                str(filepath),
                sample_rate=SPEECH_CONFIG['sample_rate'],
            ):
                return filepath
        except Exception as e:
            logging.error("Error saving transcription audio clip: %s", e)
        return None

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
                        record_uuid = str(uuid.uuid4())
                        audio_path = None
                        audio_data = transcription.get('audio_data')
                        if audio_data is not None and len(audio_data) > 0:
                            saved = self._save_transcription_audio(audio_data, record_uuid)
                            if saved:
                                audio_path = str(saved)

                        audio_start = transcription.get('chunk_start')
                        if not isinstance(audio_start, datetime):
                            audio_start = None

                        # Store in database
                        transcription_uuid = self.database.insert_audio_transcription(
                            text=cleaned_text,
                            confidence=confidence,
                            duration=duration,
                            audio_path=audio_path,
                            channel_name=self.channel_name,
                            record_uuid=record_uuid,
                            timestamp=audio_start,
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
        """Calculate hash of frame for DB / duplicate linking"""
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
    
    def _save_screenshot(
        self,
        frame: np.ndarray,
        timestamp: datetime,
        region_name: str,
        box=None,
        det_conf=None,
    ) -> Optional[Path]:
        """Save full-frame screenshot (region crops belong in ocr_crops/)."""
        try:
            vis = frame
            if box is not None and len(box) == 4:
                x1, y1, x2, y2 = (int(v) for v in box)
                if x2 > x1 and y2 > y1:
                    vis = frame.copy()
                    color = (0, 255, 0)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
                    if det_conf:
                        caption = f"{float(det_conf):.2f}"
                        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
                        (_tw, th), _ = cv2.getTextSize(caption, font, scale, thick)
                        ly = y1 - 4 if y1 > th + 8 else y1 + th + 4
                        cv2.putText(
                            vis, caption, (x1 + 2, ly), font, scale, color, thick, cv2.LINE_AA
                        )
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{region_name}_{self.channel_name}.jpg"
            filepath = STORAGE_CONFIG['screenshots_dir'] / filename
            cv2.imwrite(str(filepath), vis)
            return filepath
        except Exception as e:
            logging.error(f"Error saving screenshot: {e}")
            return None

    def _save_ollama_rejected(
        self,
        image: np.ndarray,
        timestamp: datetime,
        region_name: str,
        utr_conf: float,
        ollama_conf: float,
        draft_text: str,
        ollama_text: str,
        save_min: float,
    ) -> Optional[Path]:
        """Persist crop + metadata for Ollama replies below save_min_confidence."""
        if not OLLAMA_OCR_CONFIG.get("save_rejected", True):
            return None
        if image is None or getattr(image, "size", 0) == 0:
            return None
        try:
            out_dir = Path(STORAGE_CONFIG["ollama_rejected_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_channel = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in (self.channel_name or "channel")
            )
            safe_region = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in (region_name or "region")
            )
            stamp = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            stem = (
                f"{stamp}_{safe_region}_{safe_channel}"
                f"_utr{utr_conf:.2f}_ollama{ollama_conf:.2f}"
            )
            img_path = out_dir / f"{stem}.jpg"
            quality = int(OLLAMA_OCR_CONFIG.get("jpeg_quality", 95))
            cv2.imwrite(str(img_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            meta_path = out_dir / f"{stem}.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": timestamp.isoformat(),
                        "channel": self.channel_name,
                        "region": region_name,
                        "utrnet_confidence": round(float(utr_conf), 4),
                        "ollama_confidence": round(float(ollama_conf), 4),
                        "save_min_confidence": float(save_min),
                        "draft_text": draft_text,
                        "ollama_text": ollama_text,
                        "image": img_path.name,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return img_path
        except Exception as e:
            logging.warning(f"Failed to save Ollama rejected crop ({region_name}): {e}")
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
                    severity='high' if any(kw in ['عاجل', 'breaking'] for kw in matched_keywords) else 'medium',
                    channel_name=self.channel_name,
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
                    severity='high' if any(kw in ['عاجل', 'breaking'] for kw in matched_keywords) else 'medium',
                    channel_name=self.channel_name,
                )
                
                if alert_uuid:
                    self.stats['alerts_triggered'] += 1
                    self.alert_system.trigger_notifications(alert_uuid, text, matched_keywords)
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics"""
        current_time = datetime.now()
        runtime = (current_time - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0
        
        stats = self.stats.copy()
        start_time = self.stats.get('start_time')
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
            # JSON-safe (Socket.IO /api payloads)
            'start_time': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
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
        self.database = NewsDatabase()
        if channel_configs is None:
            from config import DEFAULT_RTSP_CHANNELS, apply_rtsp_channels
            self.database.seed_rtsp_channels(DEFAULT_RTSP_CHANNELS)
            loaded = self.database.get_rtsp_channels()
            apply_rtsp_channels(loaded)
            channel_configs = loaded or dict(RTSP_CHANNELS)
        self.channel_configs = channel_configs
        self.monitors = {}
        self.is_running = False
        self.alert_system = AlertSystem(self.database)
        self.shared_ocr = SharedOcrService()
        self.shared_ollama = SharedOllamaOcrService()
        self.shared_speech = SharedSpeechService()
        # Channel id that owns the shared Whisper / audio-capture thread
        self._speech_channel_id: Optional[str] = None

        # Initialize monitors for enabled channels
        self._initialize_monitors()

        logging.info(
            "Multi-channel monitor initialized with %s channels (shared OCR + Ollama)",
            len(self.monitors),
        )

    def _make_monitor(self, config: Dict) -> NewsMonitor:
        """Create a channel monitor that uses the shared UTRNet instance."""
        return NewsMonitor(
            rtsp_url=config["rtsp_url"],
            channel_name=config["name"],
            speech_enabled=False,
            text_regions=config.get("text_regions"),
            shared_ocr=self.shared_ocr,
            shared_ollama=self.shared_ollama,
            shared_speech=self.shared_speech,
        )

    def _initialize_monitors(self):
        """Initialize individual monitors for each enabled channel"""
        for channel_id, config in self.channel_configs.items():
            if config.get("enabled", False):
                try:
                    self.monitors[channel_id] = self._make_monitor(config)
                    logging.info("Initialized monitor for channel: %s", config["name"])
                except Exception as e:
                    logging.error(f"Failed to initialize monitor for {config['name']}: {e}")

    def any_channel_running(self) -> bool:
        return any(m.is_running for m in self.monitors.values())

    def _wait_for_processing_ready(self, monitor: "NewsMonitor", timeout: float = 120.0) -> bool:
        """Block until shared OCR is attached and the channel processing thread is running."""
        deadline = time.time() + (15.0 if monitor.audio_only else timeout)
        while self.is_running and time.time() < deadline:
            proc = monitor.processing_thread
            if monitor.audio_only:
                if monitor.is_running and proc is not None and proc.is_alive():
                    return True
            elif monitor.utr_predictor is not None and proc is not None and proc.is_alive():
                return True
            err = (monitor.stream_error or "").lower()
            if err and not err.startswith("loading ocr") and not err.startswith("starting"):
                if any(k in err for k in ("failed", "error", "cuda", "out of memory", "oom")):
                    return False
            if not monitor.is_running and monitor.utr_predictor is None and not monitor.audio_only:
                return False
            time.sleep(0.5)
        if monitor.audio_only:
            return bool(
                monitor.is_running
                and monitor.processing_thread is not None
                and monitor.processing_thread.is_alive()
            )
        return (
            monitor.utr_predictor is not None
            and monitor.processing_thread is not None
            and monitor.processing_thread.is_alive()
        )

    def start_monitoring(self):
        """Start monitoring all enabled channels using one shared UTRNet."""
        if self.is_running or self.any_channel_running():
            logging.warning("Multi-channel monitoring is already running")
            return

        self.is_running = True

        def _start_all():
            started = 0
            first_ready: Optional["NewsMonitor"] = None
            try:
                needs_ocr = any(not m.audio_only for m in self.monitors.values())
                if needs_ocr:
                    logging.info("Loading shared UTRNet for all channels…")
                    self.shared_ocr.ensure_loaded()
                    if OLLAMA_OCR_CONFIG.get("enabled", True):
                        self.shared_ollama.ensure_loaded()
                else:
                    logging.info("Audio-only channels — skipping OCR load")
            except Exception as e:
                logging.error("Shared OCR failed to load: %s", e)
                self.is_running = False
                return

            try:
                for channel_id, monitor in list(self.monitors.items()):
                    if not self.is_running:
                        break
                    try:
                        logging.info("Starting channel %s…", monitor.channel_name)
                        monitor.start_monitoring()
                        ready = self._wait_for_processing_ready(monitor)
                        if ready:
                            started += 1
                            if first_ready is None:
                                first_ready = monitor
                            logging.info(
                                "Processing ready for %s — starting next channel",
                                monitor.channel_name,
                            )
                        else:
                            logging.error(
                                "Processing not ready for %s (%s) — continuing with others",
                                monitor.channel_name,
                                monitor.stream_error,
                            )
                        time.sleep(0.25)
                    except Exception as e:
                        logging.error(f"Failed to start monitor for {channel_id}: {e}")

                logging.info(
                    "Multi-channel monitoring active: %s/%s channels (shared OCR)",
                    started,
                    len(self.monitors),
                )

                # Audio AFTER shared OCR is loaded (prevents GPU OOM crash)
                if self.is_running and SPEECH_CONFIG.get("enabled", True):
                    self._ensure_speech(preferred=first_ready)

            except Exception as e:
                logging.error(f"Multi-channel boot error: {e}")

        threading.Thread(
            target=_start_all, daemon=True, name="multi-channel-boot"
        ).start()

    def stop_monitoring(self):
        """Stop monitoring all channels"""
        logging.info("Stopping multi-channel monitoring...")

        self.is_running = False

        for channel_id, monitor in self.monitors.items():
            try:
                monitor.stop_monitoring()
                logging.info(f"Stopped monitoring for channel: {monitor.channel_name}")
            except Exception as e:
                logging.error(f"Error stopping monitor for {channel_id}: {e}")

        self.shared_ocr.cleanup()
        self.shared_speech.cleanup()

        logging.info("Multi-channel monitoring stopped")

    def clear_queues(self) -> Dict[str, int]:
        """Empty frame/audio queues on every channel monitor."""
        totals = {"frames": 0, "audio": 0}
        for monitor in self.monitors.values():
            try:
                dropped = monitor.clear_queues()
                totals["frames"] += dropped.get("frames", 0)
                totals["audio"] += dropped.get("audio", 0)
            except Exception as e:
                logging.warning("Failed to clear queues on %s: %s", monitor.channel_name, e)
        return totals

    def get_statistics(self) -> Dict:
        """Get combined statistics for all channels"""
        total_stats = {
            'frames_processed': 0,
            'frames_captured': 0,
            'text_extractions': 0,
            'audio_transcriptions': 0,
            'alerts_triggered': 0,
            'channels_running': 0,
            'channels_total': len(self.monitors),
            'start_time': None,
            'channel_stats': {},
            'is_running': self.is_running or self.any_channel_running(),
            'channel_name': 'multi_channel',
            'stream_error': None,
            'queue_sizes': {'frames': 0, 'audio': 0},
        }

        stream_errors = []

        for channel_id, monitor in self.monitors.items():
            try:
                channel_stats = monitor.get_statistics()
                total_stats['channel_stats'][channel_id] = channel_stats

                total_stats['frames_processed'] += channel_stats.get('frames_processed', 0)
                total_stats['frames_captured'] += channel_stats.get('frames_captured', 0)
                total_stats['text_extractions'] += channel_stats.get('text_extractions', 0)
                total_stats['audio_transcriptions'] += channel_stats.get('audio_transcriptions', 0)
                total_stats['alerts_triggered'] += channel_stats.get('alerts_triggered', 0)

                qs = channel_stats.get('queue_sizes') or {}
                total_stats['queue_sizes']['frames'] += qs.get('frames', 0)
                total_stats['queue_sizes']['audio'] += qs.get('audio', 0)

                if channel_stats.get('is_running', False):
                    total_stats['channels_running'] += 1

                err = channel_stats.get('stream_error')
                if err:
                    stream_errors.append(f"{monitor.channel_name}: {err}")

                if channel_stats.get('start_time') and not total_stats['start_time']:
                    total_stats['start_time'] = channel_stats['start_time']
                elif (channel_stats.get('start_time') and total_stats['start_time'] and
                      channel_stats['start_time'] < total_stats['start_time']):
                    total_stats['start_time'] = channel_stats['start_time']

            except Exception as e:
                logging.error(f"Error getting statistics for {channel_id}: {e}")

        if stream_errors:
            total_stats['stream_error'] = '; '.join(stream_errors[:4])
            if len(stream_errors) > 4:
                total_stats['stream_error'] += f' (+{len(stream_errors) - 4} more)'

        if total_stats['start_time']:
            st = total_stats['start_time']
            if isinstance(st, datetime):
                runtime = (datetime.now() - st).total_seconds()
                total_stats['start_time'] = st.isoformat()
            elif isinstance(st, str):
                try:
                    runtime = (datetime.now() - datetime.fromisoformat(st)).total_seconds()
                except ValueError:
                    runtime = 0
            else:
                runtime = 0
            total_stats['runtime_seconds'] = runtime
        else:
            total_stats['runtime_seconds'] = 0

        # Nested channel_stats may still carry datetime — normalize
        for ch_stats in total_stats.get('channel_stats', {}).values():
            st = ch_stats.get('start_time')
            if isinstance(st, datetime):
                ch_stats['start_time'] = st.isoformat()

        return total_stats

    def get_channel_status(self) -> Dict:
        """Get status of all channels"""
        status = {
            'overall_running': self.is_running or self.any_channel_running(),
            'channels': {}
        }

        for channel_id, monitor in self.monitors.items():
            try:
                channel_stats = monitor.get_statistics()
                status['channels'][channel_id] = {
                    'name': monitor.channel_name,
                    'running': channel_stats.get('is_running', False),
                    'rtsp_url': monitor.source_url,
                    'frames_processed': channel_stats.get('frames_processed', 0),
                    'frames_captured': channel_stats.get('frames_captured', 0),
                    'text_extractions': channel_stats.get('text_extractions', 0),
                    'audio_transcriptions': channel_stats.get('audio_transcriptions', 0),
                    'alerts_triggered': channel_stats.get('alerts_triggered', 0),
                    'stream_error': channel_stats.get('stream_error'),
                }
            except Exception as e:
                status['channels'][channel_id] = {
                    'name': monitor.channel_name,
                    'running': False,
                    'error': str(e)
                }

        return status

    def _speech_host_alive(self) -> bool:
        """True if the current speech host still has a live audio thread."""
        if not self._speech_channel_id:
            return False
        mon = self.monitors.get(self._speech_channel_id)
        if not mon or not mon.is_running:
            return False
        thread = getattr(mon, 'audio_thread', None)
        return bool(thread and thread.is_alive() and mon.speech_transcriber)

    def _ensure_speech(self, preferred: Optional["NewsMonitor"] = None) -> bool:
        """Start speech on every audio-only channel, plus one TV channel."""
        if not SPEECH_CONFIG.get('enabled', True):
            return False

        started_any = False
        for mon in self.monitors.values():
            if not mon.is_running or not mon.audio_only:
                continue
            thread = getattr(mon, 'audio_thread', None)
            if thread and thread.is_alive() and mon.speech_transcriber:
                started_any = True
                continue
            try:
                logging.info("Starting audio transcription on %s…", mon.channel_name)
                if mon.start_speech_transcription():
                    started_any = True
            except Exception as e:
                logging.warning("Audio transcription skipped on %s: %s", mon.channel_name, e)

        if self._speech_host_alive():
            return True

        self._speech_channel_id = None
        candidates: List["NewsMonitor"] = []
        if (
            preferred is not None
            and preferred.is_running
            and not preferred.audio_only
        ):
            candidates.append(preferred)
        for cid, mon in self.monitors.items():
            if preferred is not None and mon is preferred:
                continue
            if mon.audio_only:
                continue
            if mon.is_running and self.channel_configs.get(cid, {}).get('enabled', True):
                candidates.append(mon)

        for mon in candidates:
            try:
                logging.info("Starting deferred speech on %s…", mon.channel_name)
                if mon.start_speech_transcription():
                    for cid, m in self.monitors.items():
                        if m is mon:
                            self._speech_channel_id = cid
                            break
                    logging.info("Audio transcription active on %s", mon.channel_name)
                    return True
                logging.warning("Audio transcription failed to start on %s", mon.channel_name)
            except Exception as e:
                logging.warning("Audio transcription skipped on %s: %s", mon.channel_name, e)
        if started_any:
            return True
        logging.warning("No channel available for audio transcription")
        return False

    def set_channel_enabled(self, channel_id: str, enabled: bool) -> bool:
        """Enable/disable a channel at runtime (starts/stops its monitor)."""
        if channel_id not in self.channel_configs:
            return False

        self.channel_configs[channel_id]['enabled'] = enabled
        was_speech_host = self._speech_channel_id == channel_id

        if enabled:
            if channel_id not in self.monitors:
                cfg = self.channel_configs[channel_id]
                self.monitors[channel_id] = self._make_monitor(cfg)
            if self.is_running and not self.monitors[channel_id].is_running:
                self.monitors[channel_id].start_monitoring()
            if self.is_running and not self._speech_host_alive():
                self._ensure_speech(preferred=self.monitors.get(channel_id))
        else:
            monitor = self.monitors.get(channel_id)
            if monitor and monitor.is_running:
                monitor.stop_monitoring()
            if was_speech_host:
                self._speech_channel_id = None
                if self.is_running:
                    # Keep transcription alive on another enabled channel
                    self._ensure_speech()

        return True

    def add_channel(self, channel_id: str, config: Dict):
        """Add a new channel to monitoring"""
        try:
            if channel_id in self.monitors:
                logging.warning(f"Channel {channel_id} already exists")
                return False

            self.channel_configs[channel_id] = dict(config)

            if not config.get('enabled', True):
                logging.info(f"Registered disabled channel: {config.get('name', channel_id)}")
                return True

            monitor = self._make_monitor(config)

            self.monitors[channel_id] = monitor
            logging.info(f"Added new channel: {config['name']}")

            # Start monitoring if overall system is running
            if self.is_running:
                monitor.start_monitoring()
                logging.info(f"Started monitoring for new channel: {config['name']}")
                self._ensure_speech(preferred=monitor)

            return True

        except Exception as e:
            logging.error(f"Failed to add channel {channel_id}: {e}")
            return False

    def remove_channel(self, channel_id: str):
        """Remove a channel from monitoring"""
        try:
            monitor = self.monitors.get(channel_id)
            if monitor:
                if monitor.is_running:
                    monitor.stop_monitoring()
                del self.monitors[channel_id]

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