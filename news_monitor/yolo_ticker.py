"""Local YOLO ticker detection via Ultralytics .pt (parallel to Roboflow)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from config import YOLO_TICKER_CONFIG

_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    weights = Path(YOLO_TICKER_CONFIG.get("weights") or "")
    if not weights.is_file():
        raise FileNotFoundError(f"YOLO weights not found: {weights}")
    from ultralytics import YOLO

    _model = YOLO(str(weights))
    device = YOLO_TICKER_CONFIG.get("device")
    if device:
        _model.to(device)
    logging.info("YOLO ticker loaded: %s (classes=%s)", weights.name, _model.names)
    return _model


def pick_primary(preds: list, fw: int, fh: int):
    """preds: list of (cls, conf, x1, y1, x2, y2) in pixels."""
    ocr_classes = set(YOLO_TICKER_CONFIG.get("ocr_classes") or [])
    primary_pref = tuple(YOLO_TICKER_CONFIG.get("primary_pref") or ())
    det_conf_min = float(YOLO_TICKER_CONFIG.get("det_conf_min", 0.35))

    best = None
    best_key = None
    for cls, conf, x1, y1, x2, y2 in preds:
        if cls not in ocr_classes or conf < det_conf_min:
            continue
        area = max(0, x2 - x1) * max(0, y2 - y1)
        pref = primary_pref.index(cls) if cls in primary_pref else 99
        key = (pref, -area, -conf)
        if best_key is None or key < best_key:
            best_key = key
            x1 = max(0, int(x1))
            y1 = max(0, int(y1))
            x2 = min(fw, int(x2))
            y2 = min(fh, int(y2))
            best = (cls, conf, (x1, y1, x2, y2))
    return best


def detect_primary(
    frame: np.ndarray,
    channel_name: str,
    cached_box: Optional[Tuple],
) -> Optional[Tuple[str, float, int, int, int, int]]:
    """
    Run local YOLO on frame; return (class, det_conf, x1, y1, x2, y2) in pixels.
    Reuses cached_box when detection fails.
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return None

    fh, fw = frame.shape[:2]
    primary = None
    try:
        model = _get_model()
        conf = float(YOLO_TICKER_CONFIG.get("det_conf_min", 0.35))
        imgsz = int(YOLO_TICKER_CONFIG.get("imgsz", 640))
        results = model.predict(frame, conf=conf, imgsz=imgsz, verbose=False)
        names = model.names or {}
        preds = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls.item())
                cls = names.get(cls_id, str(cls_id))
                score = float(box.conf.item())
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                preds.append((cls, score, x1, y1, x2, y2))
        primary = pick_primary(preds, fw, fh)
    except Exception as e:
        logging.warning("YOLO detect fail on %s: %s — reuse last box", channel_name, e)

    if primary is not None:
        cls, det_conf, box = primary
        x1, y1, x2, y2 = box
        if x2 > x1 and y2 > y1:
            return cls, det_conf, x1, y1, x2, y2

    return _from_cached(cached_box, fw, fh)


def _from_cached(
    cached_box: Optional[Tuple],
    fw: int,
    fh: int,
) -> Optional[Tuple[str, float, int, int, int, int]]:
    if cached_box is None:
        return None
    cls, x1, y1, x2, y2 = cached_box
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(fw, int(x2)), min(fh, int(y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return cls, 0.0, x1, y1, x2, y2


def regions_from_detection(
    frame: np.ndarray,
    channel_name: str,
    cached_box: Optional[Tuple],
) -> Tuple[Optional[dict], Optional[Tuple[str, int, int, int, int]]]:
    """Build a single ticker region dict for extract_text_regions."""
    hit = detect_primary(frame, channel_name, cached_box)
    if hit is None:
        return None, cached_box

    cls, det_conf, x1, y1, x2, y2 = hit
    h, w = frame.shape[:2]
    new_cache = (cls, x1, y1, x2, y2)
    regions = {
        "ticker": {
            "name": cls or "Bottom Ticker",
            "region": (x1 / w, y1 / h, x2 / w, y2 / h),
            "priority": "high",
            "min_confidence": 0.7,
            "direct_ocr": True,
            "det_conf": det_conf,
        }
    }
    return regions, new_cache
