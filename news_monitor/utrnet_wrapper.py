"""
UTRNet Wrapper for Real-time Urdu Text Recognition
Optimized for news monitoring and TV ticker extraction
"""

import sys
import os
import math
import re
import hashlib
from collections import Counter
from pathlib import Path
import torch
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional, Set
import cv2
import logging

# Add UTRNet directory to path
sys.path.append(str(os.path.join(os.path.dirname(__file__), '../UTRNet-High-Resolution-Urdu-Text-Recognition-main/UTRNet-High-Resolution-Urdu-Text-Recognition-main')))

try:
    from model import Model
    from dataset import NormalizePAD
    from utils import CTCLabelConverter, AttnLabelConverter
except ImportError as e:
    logging.error(f"Failed to import UTRNet modules: {e}")
    sys.exit(1)

from config import (
    UTRNET_CONFIG,
    WEIGHTS_PATH,
    URDU_GLYPHS_PATH,
    PROCESSING_CONFIG,
    STORAGE_CONFIG,
)
import threading

_ARABIC_URDU_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

class UTRNetPredictor:
    """
    UTRNet wrapper for real-time Urdu text recognition
    Optimized for processing news channel frames
    """
    
    def __init__(self, device='cuda', batch_size=4):
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.batch_size = batch_size
        self.model = None
        self.converter = None
        self.transform = None
        self.character_set = None
        self._infer_lock = threading.Lock()
        
        self._load_character_set()
        self._initialize_model()
        
        logging.info(f"UTRNet initialized on {self.device}")
    
    def _load_character_set(self):
        """Load Urdu character set from file"""
        try:
            with open(URDU_GLYPHS_PATH, 'r', encoding='utf-8') as f:
                content = f.readlines()
            self.character_set = ''.join([elem.strip() for elem in content]) + " "
            logging.info(f"Loaded {len(self.character_set)} Urdu characters")
        except Exception as e:
            logging.error(f"Failed to load character set: {e}")
            raise
    
    def _initialize_model(self):
        """Initialize UTRNet model with pretrained weights"""
        # Create options object
        class Options:
            def __init__(self, device, character_set):
                for key, value in UTRNET_CONFIG.items():
                    setattr(self, key, value)
                self.device = device
                self.character = character_set
        
        opt = Options(self.device, self.character_set)
        
        # Initialize converter
        if opt.Prediction == 'CTC':
            self.converter = CTCLabelConverter(opt.character)
        else:
            self.converter = AttnLabelConverter(opt.character)
        
        opt.num_class = len(self.converter.character)
        
        # Initialize model
        self.model = Model(opt)
        self.model = self.model.to(self.device)
        
        # Load pretrained weights
        try:
            self.model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=self.device))
            self.model.eval()
            logging.info("Loaded UTRNet pretrained weights")
        except Exception as e:
            logging.error(f"Failed to load model weights: {e}")
            raise
        
        # Initialize image transform
        self.transform = NormalizePAD((1, opt.imgH, opt.imgW))
    
    def preprocess_image(self, image: np.ndarray) -> torch.Tensor:
        """
        Preprocess image for UTRNet inference
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
        
        Returns:
            Preprocessed tensor ready for model
        """
        # Convert BGR to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        if isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image)
        else:
            pil_image = image
        
        # Convert to grayscale
        pil_image = pil_image.convert('L')
        
        # Flip for RTL text (Urdu)
        pil_image = pil_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        
        # Resize maintaining aspect ratio
        w, h = pil_image.size
        ratio = w / float(h)
        target_h = UTRNET_CONFIG['imgH']
        target_w = UTRNET_CONFIG['imgW']
        
        if math.ceil(target_h * ratio) > target_w:
            resized_w = target_w
        else:
            resized_w = math.ceil(target_h * ratio)
        
        pil_image = pil_image.resize((resized_w, target_h), Image.Resampling.BICUBIC)
        
        # Apply normalization and padding
        tensor = self.transform(pil_image)
        
        return tensor.unsqueeze(0)  # Add batch dimension
    
    def predict_single(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Predict text from a single image
        
        Args:
            image: Input image as numpy array
        
        Returns:
            Tuple of (predicted_text, confidence_score)
        """
        try:
            # Preprocess image
            tensor = self.preprocess_image(image)
            tensor = tensor.to(self.device)
            
            # Model inference
            with torch.no_grad():
                preds = self.model(tensor)
                preds_size = torch.IntTensor([preds.size(1)] * tensor.size(0))
                
                # Get predictions
                _, preds_index = preds.max(2)
                pred_str = self.converter.decode(preds_index.data, preds_size.data)[0]
                
                # Calculate confidence score
                preds_prob = torch.softmax(preds, dim=2)
                preds_max_prob, _ = preds_prob.max(dim=2)
                
                try:
                    confidence = preds_max_prob[0].mean().item()
                except:
                    confidence = 0.0
                
                return pred_str, confidence
                
        except Exception as e:
            logging.error(f"Error in prediction: {e}")
            return "", 0.0
    
    def predict_batch(self, images: List[np.ndarray]) -> List[Tuple[str, float]]:
        """
        Predict text from a batch of images
        
        Args:
            images: List of input images as numpy arrays
        
        Returns:
            List of (predicted_text, confidence_score) tuples
        """
        if not images:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(images), self.batch_size):
            batch_images = images[i:i + self.batch_size]
            batch_results = self._process_batch(batch_images)
            results.extend(batch_results)
        
        return results
    
    def _process_batch(self, images: List[np.ndarray]) -> List[Tuple[str, float]]:
        """Process a batch of images"""
        try:
            # Preprocess all images
            tensors = []
            for img in images:
                tensor = self.preprocess_image(img)
                tensors.append(tensor)
            
            # Stack tensors
            batch_tensor = torch.cat(tensors, dim=0).to(self.device)
            
            # Model inference
            with torch.no_grad():
                preds = self.model(batch_tensor)
                preds_size = torch.IntTensor([preds.size(1)] * batch_tensor.size(0))
                
                # Get predictions
                _, preds_index = preds.max(2)
                pred_strs = self.converter.decode(preds_index.data, preds_size.data)
                
                # Calculate confidence scores
                preds_prob = torch.softmax(preds, dim=2)
                preds_max_prob, _ = preds_prob.max(dim=2)
                
                results = []
                for i, pred_str in enumerate(pred_strs):
                    try:
                        confidence = preds_max_prob[i].mean().item()
                    except:
                        confidence = 0.0
                    results.append((pred_str, confidence))
                
                return results
                
        except Exception as e:
            logging.error(f"Error in batch prediction: {e}")
            return [("", 0.0) for _ in images]
    
    def extract_text_regions(
        self,
        frame: np.ndarray,
        regions: dict,
        channel_name: Optional[str] = None,
    ) -> dict:
        """
        Extract text from specific regions of the frame (tickers, headlines, etc.)
        
        Args:
            frame: Input video frame
            regions: Dictionary of region definitions
            channel_name: Optional channel label used when saving debug crops
        
        Returns:
            Dictionary with region names as keys and extraction results as values
        """
        results = {}
        h, w = frame.shape[:2]
        
        for region_name, region_config in regions.items():
            try:
                # Extract region coordinates
                x1, y1, x2, y2 = region_config['region']
                x1, y1, x2, y2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
                
                # Extract region
                region_img = frame[y1:y2, x1:x2]
                min_h = int(PROCESSING_CONFIG.get('min_region_height_px', 22))
                min_w = int(PROCESSING_CONFIG.get('min_region_width_px', 80))
                # Tiny Settings boxes (disabled headline/side) → no enhance / save / OCR
                if (
                    region_img.size == 0
                    or region_img.shape[0] < min_h
                    or region_img.shape[1] < min_w
                ):
                    results[region_name] = {
                        'text': '',
                        'confidence': 0.0,
                        'region': (x1, y1, x2, y2),
                        'priority': region_config.get('priority', 'medium'),
                        'skipped': 'too_small',
                    }
                    continue

                if not region_likely_contains_text(region_img):
                    results[region_name] = {
                        'text': '',
                        'confidence': 0.0,
                        'region': (x1, y1, x2, y2),
                        'priority': region_config.get('priority', 'medium'),
                    }
                    continue

                # Raw frame crop; optionally preprocess before UTRNet / Ollama
                raw_hash = _ocr_crop_content_hash(region_img)
                _save_ocr_crop(
                    region_img,
                    region_name,
                    channel_name,
                    suffix="raw",
                    base_hash=raw_hash,
                )
                preprocess_mode = resolve_ocr_preprocess_mode()
                ocr_input = preprocess_region_for_ocr(region_img)
                if preprocess_mode != "none":
                    # Same original hash + "_clear_text_hd" so HD pairs with raw
                    _save_ocr_crop(
                        ocr_input,
                        region_name,
                        channel_name,
                        suffix=preprocess_mode,
                        base_hash=raw_hash,
                    )
                with self._infer_lock:
                    text, confidence = self.predict_single(ocr_input)

                # Always return prediction + confidence. Pipeline decides:
                # high (≥98%) keep, mid (80–98%) Ollama refine, low discard.
                results[region_name] = {
                    'text': (text or '').strip(),
                    'confidence': float(confidence),
                    'region': (x1, y1, x2, y2),
                    'priority': region_config.get('priority', 'medium'),
                    'region_min_confidence': float(
                        region_config.get('min_confidence', 0.5)
                    ),
                    # Same pixels UTRNet saw — reuse for Ollama / screenshots
                    'ocr_image': ocr_input,
                    'ocr_preprocess': preprocess_mode,
                }

            except Exception as e:
                logging.error(f"Error processing region {region_name}: {e}")
                results[region_name] = {
                    'text': '',
                    'confidence': 0.0,
                    'region': (0, 0, 0, 0),
                    'priority': region_config.get('priority', 'medium')
                }
        
        return results

    def cleanup(self):
        """Cleanup resources"""
        if self.model:
            del self.model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        logging.info("UTRNet resources cleaned up")


class SharedOcrService:
    """One UTRNet instance shared across all channel monitors."""

    def __init__(self):
        self._predictor: Optional[UTRNetPredictor] = None
        self._lock = threading.Lock()
        self._load_error: Optional[str] = None

    def ensure_loaded(self) -> UTRNetPredictor:
        """Load UTRNet once; safe to call from multiple threads."""
        if self._predictor is not None:
            return self._predictor
        with self._lock:
            if self._predictor is not None:
                return self._predictor
            try:
                self._load_error = None
                self._predictor = UTRNetPredictor(
                    device="cuda",
                    batch_size=PROCESSING_CONFIG["batch_size"],
                )
                logging.info("Shared UTRNet model initialized for multi-channel OCR")
                return self._predictor
            except Exception as e:
                self._load_error = str(e)
                logging.error("Failed to initialize shared UTRNet: %s", e)
                raise

    def is_ready(self) -> bool:
        return self._predictor is not None

    def get_load_error(self) -> Optional[str]:
        return self._load_error

    def cleanup(self):
        with self._lock:
            if self._predictor is not None:
                self._predictor.cleanup()
                self._predictor = None
            self._load_error = None
            logging.info("Shared UTRNet resources cleaned up")


def _safe_filename_part(value: str, fallback: str = "unknown") -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", (value or "").strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("_")
    return cleaned or fallback


# Content hashes of OCR crops already written this process (avoids re-stat/re-write)
# Keys are "{base_hash}_{stage}" so raw + clear_text_hd share one original id
_saved_ocr_crop_keys: Set[str] = set()
_saved_ocr_crop_keys_lock = threading.Lock()


def _ocr_crop_content_hash(region_img: np.ndarray) -> str:
    """Stable MD5 of crop pixels (shape + dtype + bytes)."""
    arr = np.ascontiguousarray(region_img)
    h = hashlib.md5()
    h.update(str(arr.shape).encode("ascii"))
    h.update(str(arr.dtype).encode("ascii"))
    h.update(arr.tobytes())
    return h.hexdigest()


def _save_ocr_crop(
    region_img: np.ndarray,
    region_name: str,
    channel_name: Optional[str] = None,
    suffix: str = "raw",
    base_hash: Optional[str] = None,
) -> Optional[Path]:
    """
    Persist OCR region crops for debugging.

    Filenames share the original (raw) content hash so pairs match:
      {raw_hash}_Channel_ticker_raw.png
      {raw_hash}_Channel_ticker_clear_text_hd.png
    """
    if not PROCESSING_CONFIG.get("save_ocr_crops", False):
        return None
    try:
        # Always key/name from the original crop hash when provided
        name_hash = base_hash or _ocr_crop_content_hash(region_img)
        stage = _safe_filename_part(suffix, "raw")
        dedupe_key = f"{name_hash}_{stage}"
        with _saved_ocr_crop_keys_lock:
            if dedupe_key in _saved_ocr_crop_keys:
                return None

        crops_dir = Path(STORAGE_CONFIG["ocr_crops_dir"])
        crops_dir.mkdir(parents=True, exist_ok=True)
        channel_part = _safe_filename_part(channel_name or "channel")
        region_part = _safe_filename_part(region_name, "region")
        filepath = crops_dir / f"{name_hash}_{channel_part}_{region_part}_{stage}.png"
        if filepath.exists():
            with _saved_ocr_crop_keys_lock:
                _saved_ocr_crop_keys.add(dedupe_key)
            return filepath

        cv2.imwrite(str(filepath), region_img)
        with _saved_ocr_crop_keys_lock:
            _saved_ocr_crop_keys.add(dedupe_key)
        return filepath
    except Exception as e:
        logging.warning(f"Failed to save OCR crop ({region_name}): {e}")
        return None


# Utility functions for text processing
def resolve_ocr_preprocess_mode() -> str:
    """Return active OCR crop preprocess mode (none | clahe_otsu | clear_text_hd)."""
    mode = str(PROCESSING_CONFIG.get("ocr_preprocess") or "none").strip().lower()
    if mode not in ("none", "clahe_otsu", "clear_text_hd"):
        mode = "none"
    # Legacy flag: ocr_enhance_crop=True with mode none → clahe_otsu
    if mode == "none" and PROCESSING_CONFIG.get("ocr_enhance_crop", False):
        return "clahe_otsu"
    return mode


def enhance_region_for_ocr(region_img: np.ndarray) -> np.ndarray:
    """Upscale and boost contrast on ticker crops (helps YouTube compression)."""
    h, w = region_img.shape[:2]
    target_h = max(h, 48)
    if h < target_h:
        scale = target_h / float(h)
        region_img = cv2.resize(
            region_img,
            (int(w * scale), target_h),
            interpolation=cv2.INTER_CUBIC,
        )

    gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def enhance_region_clear_text_hd(region_img: np.ndarray) -> np.ndarray:
    """Color-preserving upscale + denoise + sharpen for clearer ticker text."""
    img = region_img
    h, w = img.shape[:2]
    if h < 1 or w < 1:
        return region_img

    # Upscale short ticker bands so glyphs are easier for OCR / vision models
    target_h = max(h * 2, 64) if h < 64 else h
    if h < target_h:
        scale = target_h / float(h)
        new_w = int(w * scale)
        # Cap extreme widths on full-bleed tickers
        if new_w > 1920:
            scale = 1920 / float(w)
            target_h = max(1, int(h * scale))
            new_w = 1920
        img = cv2.resize(
            img,
            (max(1, new_w), max(1, target_h)),
            interpolation=cv2.INTER_CUBIC,
        )

    # Mild NL-means: strip compression grain without melting Urdu strokes
    img = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)

    # Unsharp mask for crisper glyph edges
    blur = cv2.GaussianBlur(img, (0, 0), sigmaX=1.0)
    img = cv2.addWeighted(img, 1.45, blur, -0.45, 0)
    return img


def preprocess_region_for_ocr(region_img: np.ndarray) -> np.ndarray:
    """Apply configured OCR crop preprocess (or return raw)."""
    mode = resolve_ocr_preprocess_mode()
    if mode == "clahe_otsu":
        return enhance_region_for_ocr(region_img)
    if mode == "clear_text_hd":
        return enhance_region_clear_text_hd(region_img)
    return region_img


def region_likely_contains_text(region_img: np.ndarray) -> bool:
    """Skip uniform/blank bands (video background mistaken for ticker)."""
    gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
    if float(np.std(gray)) < 14.0:
        return False
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = float(np.count_nonzero(edges)) / max(edges.size, 1)
    return edge_ratio >= 0.01


def is_plausible_urdu_text(
    text: str, min_length: int = 6, min_long_words: int = 1
) -> bool:
    """Reject OCR garbage: too short, or not enough real Urdu script."""
    if not text:
        return False

    compact = text.replace(" ", "")
    if len(compact) < min_length:
        return False

    urdu_chars = len(_ARABIC_URDU_RE.findall(text))
    if urdu_chars < min_length:
        return False

    # Allow digits and Latin tokens in tickers; ratio uses Urdu vs other letters only
    script_compact = re.sub(r"[\d.٪%٬:/\-A-Za-z@#]+", "", compact)
    if script_compact and urdu_chars / max(len(script_compact), 1) < 0.7:
        return False
    # Still require a solid Urdu core (reject English-only UI garbage)
    if urdu_chars / max(len(compact), 1) < 0.45:
        return False

    counts = Counter(compact)
    if counts and counts.most_common(1)[0][1] / len(compact) > 0.45:
        return False

    words = [w for w in text.split() if len(w) > 1]
    if not words:
        return False
    long_words = [w for w in words if len(w) >= 3]
    if len(long_words) < min_long_words:
        return False
    if len(words) == 1 and len(words[0]) < 8:
        return False

    return True


def clean_urdu_text(text: str) -> str:
    """Clean and normalize extracted ticker text (Urdu + digits + English words)."""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())

    # Keep Urdu, digits, and Latin words (e.g. highest, KSE). Drop only @#
    text = re.sub(r"[@#]+", " ", text)
    text = ' '.join(text.split())

    # Remove isolated single characters (likely OCR errors); keep digits and letters
    words = text.split()
    cleaned_words = [
        word for word in words
        if len(word) > 1 or word in ['و', 'ا'] or word.isdigit()
    ]

    return ' '.join(cleaned_words)

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two text strings"""
    if not text1 or not text2:
        return 0.0
    
    # Simple character-based similarity
    set1 = set(text1.replace(' ', ''))
    set2 = set(text2.replace(' ', ''))
    
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0