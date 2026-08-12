"""Roboflow ticker detection — same logic as root script.py."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from config import ROBOFLOW_CONFIG, STORAGE_CONFIG

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = (ROBOFLOW_CONFIG.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is not set")
    from inference_sdk import InferenceHTTPClient

    _client = InferenceHTTPClient(
        api_url=ROBOFLOW_CONFIG.get("api_url", "https://serverless.roboflow.com"),
        api_key=api_key,
    )
    return _client


def det_box(p: dict, fw: int, fh: int) -> Tuple[int, int, int, int]:
    x, y, w, h = p["x"], p["y"], p["width"], p["height"]
    x1 = max(0, int(x - w / 2))
    y1 = max(0, int(y - h / 2))
    x2 = min(fw, int(x + w / 2))
    y2 = min(fh, int(y + h / 2))
    return x1, y1, x2, y2


def pick_primary(preds: list, fw: int, fh: int):
    ocr_classes = set(ROBOFLOW_CONFIG.get("ocr_classes") or [])
    primary_pref = tuple(ROBOFLOW_CONFIG.get("primary_pref") or ())
    det_conf_min = float(ROBOFLOW_CONFIG.get("det_conf_min", 0.35))

    best = None
    best_key = None
    for p in preds:
        cls = p.get("class") or ""
        conf = float(p.get("confidence") or 0)
        if cls not in ocr_classes or conf < det_conf_min:
            continue
        w, h = float(p["width"]), float(p["height"])
        area = w * h
        pref = primary_pref.index(cls) if cls in primary_pref else 99
        key = (pref, -area, -conf)
        if best_key is None or key < best_key:
            best_key = key
            best = (cls, conf, det_box(p, fw, fh))
    return best


def detect_primary(
    frame: np.ndarray,
    channel_name: str,
    cached_box: Optional[Tuple],
) -> Optional[Tuple[str, float, int, int, int, int]]:
    """
    Run Roboflow on frame; return (class, det_conf, x1, y1, x2, y2) in pixels.
    Reuses cached_box when detection fails.
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return None

    fh, fw = frame.shape[:2]
    live_path = STORAGE_CONFIG["ocr_crops_dir"] / f"{channel_name}_roboflow_live.jpg"
    if not cv2.imwrite(str(live_path), frame):
        logging.warning("Roboflow: failed to write live frame for %s", channel_name)
        return _from_cached(cached_box, fw, fh)

    primary = None
    try:
        result = _get_client().infer(str(live_path), model_id=ROBOFLOW_CONFIG["model_id"])
        preds = result.get("predictions") or []
        primary = pick_primary(preds, fw, fh)
    except Exception as e:
        logging.warning("Roboflow detect fail on %s: %s — reuse last box", channel_name, e)

    if primary is not None:
        cls, conf, box = primary
        x1, y1, x2, y2 = box
        if x2 > x1 and y2 > y1:
            return cls, conf, x1, y1, x2, y2

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
