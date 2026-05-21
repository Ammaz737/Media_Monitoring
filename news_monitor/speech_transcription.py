"""
Speech Transcription Module for Urdu News Audio
Uses offline models like Whisper for real-time transcription
"""

import logging
import torch
import torchaudio
import numpy as np
from typing import List, Tuple, Optional
import threading
import queue
import time
from pathlib import Path
import tempfile
import wave

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("Whisper not available, install with: pip install openai-whisper")

try:
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Tokenizer, Wav2Vec2Processor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers not available, install with: pip install transformers")

from config import SPEECH_CONFIG

class SpeechTranscriber:
    """
    Offline speech transcription for Urdu audio
    Supports multiple models: Whisper, Wav2Vec2
    """
    
    def __init__(self, model_name: str = None, device: str = 'cuda'):
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.model_name = model_name or SPEECH_CONFIG['model']
        self.model = None
        self.processor = None
        self.sample_rate = SPEECH_CONFIG['sample_rate']
        
        self._load_model()
        logging.info(f"Speech transcriber initialized with {self.model_name} on {self.device}")
    
    def _load_model(self):
        """Load the specified speech recognition model"""
        try:
            if 'whisper' in self.model_name.lower():
                self._load_whisper_model()
            elif 'wav2vec2' in self.model_name.lower():
                self._load_wav2vec2_model()
            else:
                # Default to Whisper if available
                if WHISPER_AVAILABLE:
                    self._load_whisper_model()
                elif TRANSFORMERS_AVAILABLE:
                    self._load_wav2vec2_model()
                else:
                    raise ValueError("No speech recognition models available")
                    
        except Exception as e:
            logging.error(f"Failed to load speech model: {e}")
            raise
    
    def _load_whisper_model(self):
        """Load Whisper model for transcription"""
        if not WHISPER_AVAILABLE:
            raise ImportError("Whisper not available")
        
        # Extract model size from model name
        if 'large' in self.model_name:
            model_size = 'large'
        elif 'medium' in self.model_name:
            model_size = 'medium'
        elif 'small' in self.model_name:
            model_size = 'small'
        elif 'base' in self.model_name:
            model_size = 'base'
        else:
            model_size = 'small'  # Default
        
        self.model = whisper.load_model(model_size, device=self.device)
        self.model_type = 'whisper'
        logging.info(f"Loaded Whisper {model_size} model")
    
    def _load_wav2vec2_model(self):
        """Load Wav2Vec2 model for Urdu transcription"""
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers not available")
        
        # Use a multilingual or Urdu-specific model
        model_path = "facebook/wav2vec2-xlsr-53-large"  # Multilingual model
        
        try:
            self.processor = Wav2Vec2Processor.from_pretrained(model_path)
            self.model = Wav2Vec2ForCTC.from_pretrained(model_path).to(self.device)
            self.model_type = 'wav2vec2'
            logging.info(f"Loaded Wav2Vec2 model: {model_path}")
        except Exception as e:
            logging.error(f"Failed to load Wav2Vec2 model: {e}")
            raise
    
    def preprocess_audio(self, audio_data: np.ndarray, 
                        original_sr: int = None) -> np.ndarray:
        """
        Preprocess audio data for transcription
        
        Args:
            audio_data: Raw audio data as numpy array
            original_sr: Original sample rate
        
        Returns:
            Preprocessed audio data
        """
        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            else:
                audio_data = audio_data.astype(np.float32)
        
        # Resample if necessary
        if original_sr and original_sr != self.sample_rate:
            # Simple resampling - for production use librosa.resample
            ratio = self.sample_rate / original_sr
            new_length = int(len(audio_data) * ratio)
            audio_data = np.interp(
                np.linspace(0, len(audio_data), new_length),
                np.arange(len(audio_data)),
                audio_data
            )
        
        # Normalize audio
        max_val = np.abs(audio_data).max()
        if max_val > 0:
            audio_data = audio_data / max_val
        
        return audio_data
    
    def transcribe_whisper(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """Transcribe audio using Whisper model for Urdu"""
        try:
            # Whisper expects audio in specific format
            # language='ur' specifically for Urdu transcription
            result = self.model.transcribe(
                audio_data,
                language='ur',  # Urdu language code
                task='transcribe',
                fp16=False,
                verbose=False,
                word_timestamps=False
            )
            
            text = result.get('text', '').strip()
            
            # Calculate average confidence from segments
            segments = result.get('segments', [])
            if segments:
                confidences = []
                for seg in segments:
                    if 'avg_logprob' in seg:
                        # Convert log probability to confidence (rough approximation)
                        conf = max(0.0, min(1.0, np.exp(seg['avg_logprob'])))
                        confidences.append(conf)
                
                if confidences:
                    confidence = np.mean(confidences)
                else:
                    confidence = 0.5  # Default confidence
            else:
                confidence = 0.5
            
            return text, confidence
            
        except Exception as e:
            logging.error(f"Whisper transcription error: {e}")
            return "", 0.0
    
    def transcribe_wav2vec2(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """Transcribe audio using Wav2Vec2 model"""
        try:
            # Process audio
            inputs = self.processor(
                audio_data, 
                sampling_rate=self.sample_rate, 
                return_tensors="pt", 
                padding=True
            )
            
            input_values = inputs.input_values.to(self.device)
            
            # Get model predictions
            with torch.no_grad():
                logits = self.model(input_values).logits
            
            # Get predicted tokens
            predicted_ids = torch.argmax(logits, dim=-1)
            
            # Decode transcription
            transcription = self.processor.batch_decode(predicted_ids)[0]
            
            # Calculate confidence (simplified)
            probs = torch.softmax(logits, dim=-1)
            max_probs = torch.max(probs, dim=-1)[0]
            confidence = torch.mean(max_probs).item()
            
            return transcription.strip(), confidence
            
        except Exception as e:
            logging.error(f"Wav2Vec2 transcription error: {e}")
            return "", 0.0
    
    def transcribe(self, audio_data: np.ndarray, 
                  original_sr: int = None) -> Tuple[str, float]:
        """
        Transcribe audio data to text
        
        Args:
            audio_data: Audio data as numpy array
            original_sr: Original sample rate of audio
        
        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        if len(audio_data) == 0:
            return "", 0.0
        
        # Preprocess audio
        processed_audio = self.preprocess_audio(audio_data, original_sr)
        
        # Transcribe based on model type
        if self.model_type == 'whisper':
            return self.transcribe_whisper(processed_audio)
        elif self.model_type == 'wav2vec2':
            return self.transcribe_wav2vec2(processed_audio)
        else:
            logging.error(f"Unknown model type: {self.model_type}")
            return "", 0.0
    
    def transcribe_file(self, audio_path: str) -> Tuple[str, float]:
        """
        Transcribe audio from file
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        try:
            # Load audio file
            audio_data, sample_rate = torchaudio.load(audio_path)
            
            # Convert to mono if stereo
            if audio_data.shape[0] > 1:
                audio_data = torch.mean(audio_data, dim=0)
            else:
                audio_data = audio_data.squeeze(0)
            
            # Convert to numpy
            audio_np = audio_data.numpy()
            
            return self.transcribe(audio_np, sample_rate)
            
        except Exception as e:
            logging.error(f"Error transcribing file {audio_path}: {e}")
            return "", 0.0
    
    def cleanup(self):
        """Clean up model resources"""
        if self.model:
            del self.model
        if self.processor:
            del self.processor
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        logging.info("Speech transcriber resources cleaned up")


class AudioBuffer:
    """
    Circular buffer for real-time audio processing
    Handles chunking and overlap for continuous transcription
    """
    
    def __init__(self, chunk_duration: float = 30.0, 
                 overlap: float = 5.0, 
                 sample_rate: int = 16000):
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.sample_rate = sample_rate
        
        self.chunk_size = int(chunk_duration * sample_rate)
        self.overlap_size = int(overlap * sample_rate)
        self.stride = self.chunk_size - self.overlap_size
        
        self.buffer = np.array([], dtype=np.float32)
        self.lock = threading.Lock()
    
    def add_audio(self, audio_data: np.ndarray):
        """Add audio data to buffer"""
        with self.lock:
            self.buffer = np.concatenate([self.buffer, audio_data])
    
    def get_chunks(self) -> List[np.ndarray]:
        """Get available audio chunks for processing"""
        chunks = []
        
        with self.lock:
            while len(self.buffer) >= self.chunk_size:
                # Extract chunk
                chunk = self.buffer[:self.chunk_size].copy()
                chunks.append(chunk)
                
                # Move buffer forward by stride
                self.buffer = self.buffer[self.stride:]
        
        return chunks
    
    def clear(self):
        """Clear the buffer"""
        with self.lock:
            self.buffer = np.array([], dtype=np.float32)


class RealtimeSpeechTranscriber:
    """
    Real-time speech transcription manager
    Handles continuous audio stream processing
    """
    
    def __init__(self, transcriber: SpeechTranscriber = None):
        self.transcriber = transcriber or SpeechTranscriber()
        self.audio_buffer = AudioBuffer(
            chunk_duration=SPEECH_CONFIG['chunk_duration'],
            overlap=SPEECH_CONFIG['overlap'],
            sample_rate=SPEECH_CONFIG['sample_rate']
        )
        
        self.transcription_queue = queue.Queue()
        self.is_running = False
        self.processing_thread = None
        
        # Statistics
        self.total_chunks_processed = 0
        self.total_processing_time = 0
    
    def start(self):
        """Start real-time transcription processing"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        logging.info("Real-time speech transcription started")
    
    def stop(self):
        """Stop real-time transcription processing"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
        logging.info("Real-time speech transcription stopped")
    
    def add_audio(self, audio_data: np.ndarray):
        """Add audio data for transcription"""
        if self.is_running:
            self.audio_buffer.add_audio(audio_data)
    
    def _processing_loop(self):
        """Main processing loop for transcription"""
        while self.is_running:
            try:
                chunks = self.audio_buffer.get_chunks()
                
                for chunk in chunks:
                    if not self.is_running:
                        break
                    
                    start_time = time.time()
                    
                    # Transcribe chunk
                    text, confidence = self.transcriber.transcribe(chunk)
                    
                    processing_time = time.time() - start_time
                    
                    # Update statistics
                    self.total_chunks_processed += 1
                    self.total_processing_time += processing_time
                    
                    # Add to queue if text was extracted
                    if text.strip():
                        result = {
                            'text': text.strip(),
                            'confidence': confidence,
                            'timestamp': time.time(),
                            'processing_time': processing_time,
                            'chunk_duration': len(chunk) / self.audio_buffer.sample_rate
                        }
                        self.transcription_queue.put(result)
                
                # Sleep to prevent busy waiting
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Error in transcription processing loop: {e}")
                time.sleep(1.0)
    
    def get_transcriptions(self) -> List[dict]:
        """Get available transcription results"""
        results = []
        
        try:
            while not self.transcription_queue.empty():
                results.append(self.transcription_queue.get_nowait())
        except queue.Empty:
            pass
        
        return results
    
    def get_statistics(self) -> dict:
        """Get processing statistics"""
        if self.total_chunks_processed > 0:
            avg_processing_time = self.total_processing_time / self.total_chunks_processed
        else:
            avg_processing_time = 0.0
        
        return {
            'total_chunks_processed': self.total_chunks_processed,
            'total_processing_time': self.total_processing_time,
            'avg_processing_time': avg_processing_time,
            'is_running': self.is_running,
            'queue_size': self.transcription_queue.qsize()
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        self.audio_buffer.clear()
        self.transcriber.cleanup()


# Utility functions
def save_audio_chunk(audio_data: np.ndarray, 
                    filepath: str, 
                    sample_rate: int = 16000):
    """Save audio chunk to file"""
    try:
        # Ensure audio is in correct format
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        return True
    except Exception as e:
        logging.error(f"Error saving audio chunk: {e}")
        return False

def extract_audio_from_rtsp(rtsp_url: str, 
                           duration: float = 30.0,
                           sample_rate: int = 16000) -> np.ndarray:
    """Extract audio from RTSP stream using ffmpeg"""
    import subprocess
    
    try:
        # Use ffmpeg to extract audio from RTSP stream
        # -i: input RTSP URL
        # -t: duration in seconds
        # -vn: no video
        # -ac 1: mono audio
        # -ar: sample rate
        # -f s16le: output format (16-bit signed little-endian PCM)
        # pipe:1: output to stdout
        
        command = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',  # Use TCP for more reliable connection
            '-i', rtsp_url,
            '-t', str(duration),
            '-vn',  # No video
            '-ac', '1',  # Mono
            '-ar', str(sample_rate),  # Sample rate
            '-f', 's16le',  # 16-bit signed PCM
            '-loglevel', 'quiet',  # Suppress ffmpeg logs
            'pipe:1'  # Output to stdout
        ]
        
        # Run ffmpeg and capture audio output
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8
        )
        
        # Read audio data
        audio_bytes, stderr = process.communicate(timeout=duration + 5)
        
        if process.returncode != 0:
            logging.error(f"FFmpeg error: {stderr.decode()}")
            # Return silence instead of dummy data
            samples = int(duration * sample_rate)
            return np.zeros(samples, dtype=np.float32)
        
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 and normalize to [-1, 1]
        audio_float = audio_np.astype(np.float32) / 32768.0
        
        logging.info(f"Extracted {len(audio_float)/sample_rate:.2f}s of audio from RTSP")
        
        return audio_float
        
    except subprocess.TimeoutExpired:
        logging.error(f"FFmpeg timeout after {duration}s")
        process.kill()
        samples = int(duration * sample_rate)
        return np.zeros(samples, dtype=np.float32)
        
    except Exception as e:
        logging.error(f"Error extracting audio from RTSP: {e}")
        # Return silence on error
        samples = int(duration * sample_rate)
        return np.zeros(samples, dtype=np.float32)
