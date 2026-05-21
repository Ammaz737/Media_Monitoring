"""
UTRNet Wrapper for Real-time Urdu Text Recognition
Optimized for news monitoring and TV ticker extraction
"""

import sys
import os
import math
import re
from collections import Counter
import torch
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional
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

from config import UTRNET_CONFIG, WEIGHTS_PATH, URDU_GLYPHS_PATH, PROCESSING_CONFIG

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
    
    def extract_text_regions(self, frame: np.ndarray, regions: dict) -> dict:
        """
        Extract text from specific regions of the frame (tickers, headlines, etc.)
        
        Args:
            frame: Input video frame
            regions: Dictionary of region definitions
        
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
                min_h = PROCESSING_CONFIG.get('min_region_height_px', 22)
                if region_img.size == 0 or region_img.shape[0] < min_h:
                    results[region_name] = {
                        'text': '',
                        'confidence': 0.0,
                        'region': (x1, y1, x2, y2),
                        'priority': region_config.get('priority', 'medium'),
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

                region_img = enhance_region_for_ocr(region_img)
                text, confidence = self.predict_single(region_img)

                min_conf = region_config.get('min_confidence', 0.5)
                if confidence >= min_conf and text.strip():
                    results[region_name] = {
                        'text': text.strip(),
                        'confidence': confidence,
                        'region': (x1, y1, x2, y2),
                        'priority': region_config.get('priority', 'medium'),
                    }
                else:
                    results[region_name] = {
                        'text': '',
                        'confidence': confidence,
                        'region': (x1, y1, x2, y2),
                        'priority': region_config.get('priority', 'medium'),
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


# Utility functions for text processing
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
    """Reject OCR garbage: Latin junk, too short, or non-Urdu script."""
    if not text:
        return False

    compact = text.replace(" ", "")
    if len(compact) < min_length:
        return False

    urdu_chars = len(_ARABIC_URDU_RE.findall(text))
    if urdu_chars < min_length:
        return False

    if urdu_chars / max(len(compact), 1) < 0.7:
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
    """Clean and normalize extracted Urdu text"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Strip Latin/digits (YouTube UI, timestamps, watermarks)
    text = re.sub(r"[A-Za-z0-9@#]+", " ", text)

    # Remove isolated single characters (likely OCR errors)
    words = text.split()
    cleaned_words = [word for word in words if len(word) > 1 or word in ['و', 'ا']]

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