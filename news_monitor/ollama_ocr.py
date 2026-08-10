"""
Ollama vision OCR fallback for mid-confidence UTRNet results.

Only used when UTRNet confidence is in [utrnet_min, utrnet_high).
Unreadable crops must return empty text + very low confidence and are discarded.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import urllib.error
import urllib.request

from config import OLLAMA_OCR_CONFIG

_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

_SYSTEM_PROMPT = (
    "You are an Urdu TV news ticker OCR verifier. "
    "Read ONLY what is visibly written in the image. "
    "Never invent, complete, or guess missing words."
)


def _user_prompt(draft_text: str) -> str:
    draft = (draft_text or "").strip() or "(none)"
    return (
        "This image is a crop of a Urdu news ticker or headline.\n"
        f"UTRNet draft (may be wrong — do NOT trust it if the image disagrees): {draft}\n\n"
        "Rules:\n"
        "1. Read ONLY the text visibly written in the IMAGE.\n"
        "2. If the text is clearly readable, return that exact text as written, "
        "including Urdu, English words (e.g. highest), numbers and percentages.\n"
        "3. If the text is blurry, garbled, cut off, or not readable at all: "
        "discard it — set text to an empty string and confidence between 0.0 and 0.10.\n"
        "4. Never invent, complete, or guess missing words. Never copy the draft unless "
        "it matches the image.\n"
        "5. confidence must be from 0.0 to 1.0.\n"
        "6. Respond with JSON only, no markdown:\n"
        '{"text":"...","confidence":0.0}\n'
    )


class OllamaVisionOcr:
    """Thread-safe, single-flight Ollama vision OCR helper."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = dict(OLLAMA_OCR_CONFIG)
        if config:
            self.cfg.update(config)
        self._lock = threading.Lock()
        self._busy = False
        self._available: Optional[bool] = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True))

    def utrnet_needs_ollama(self, confidence: float) -> bool:
        low = float(self.cfg.get("utrnet_min", 0.80))
        high = float(self.cfg.get("utrnet_high", 0.98))
        return low <= float(confidence) < high

    def utrnet_is_high(self, confidence: float) -> bool:
        return float(confidence) >= float(self.cfg.get("utrnet_high", 0.98))

    def utrnet_is_low(self, confidence: float) -> bool:
        return float(confidence) < float(self.cfg.get("utrnet_min", 0.80))

    def save_min_confidence(self) -> float:
        return float(self.cfg.get("save_min_confidence", 0.85))

    def ping(self) -> bool:
        """Cheap readiness check (cached until failure)."""
        if self._available is True:
            return True
        url = f"{self.cfg['base_url']}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
        return bool(self._available)

    def refine(
        self,
        image_bgr: np.ndarray,
        draft_text: str = "",
    ) -> Tuple[str, float]:
        """
        Ask Ollama to read the crop. Returns (text, confidence).
        On skip/failure returns ("", 0.0).
        """
        if not self.enabled or image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return "", 0.0

        if self.cfg.get("skip_if_busy", True):
            if not self._lock.acquire(blocking=False):
                logging.info("Ollama OCR busy — skipping mid-confidence refine")
                return "", 0.0
        else:
            self._lock.acquire()

        self._busy = True
        try:
            if not self.ping():
                logging.warning("Ollama not reachable at %s", self.cfg.get("base_url"))
                return "", 0.0
            payload = self._build_payload(image_bgr, draft_text)
            logging.info(
                "Ollama OCR calling model=%s draft_len=%s",
                payload.get("model"),
                len(draft_text or ""),
            )
            raw = self._post_generate(payload)
            text, confidence = self._parse_response(raw)
            if not text.strip():
                confidence = min(confidence, 0.05)
            logging.info(
                "Ollama OCR result conf=%.3f text_len=%s",
                confidence,
                len(text.strip()),
            )
            return text.strip(), float(confidence)
        except Exception as e:
            self._available = None
            logging.warning("Ollama OCR refine failed: %s", e)
            return "", 0.0
        finally:
            self._busy = False
            self._lock.release()

    def _encode_image(self, image_bgr: np.ndarray) -> str:
        img = image_bgr
        h, w = img.shape[:2]
        max_w = int(self.cfg.get("max_image_width", 640))
        if w > max_w and w > 0:
            scale = max_w / float(w)
            img = cv2.resize(
                img,
                (max_w, max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        quality = int(self.cfg.get("jpeg_quality", 70))
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            raise RuntimeError("Failed to JPEG-encode OCR crop for Ollama")
        return base64.b64encode(buf.tobytes()).decode("ascii")

    def _build_payload(self, image_bgr: np.ndarray, draft_text: str) -> Dict[str, Any]:
        b64 = self._encode_image(image_bgr)
        payload: Dict[str, Any] = {
            "model": self.cfg.get("model", "qwen3.6:latest"),
            "stream": False,
            "keep_alive": self.cfg.get("keep_alive", "10m"),
            "format": "json",
            # qwen3.x thinking models otherwise spend the token budget on CoT
            "think": bool(self.cfg.get("think", False)),
            "options": {
                "temperature": 0.0,
                "num_predict": int(self.cfg.get("num_predict", 120)),
            },
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _user_prompt(draft_text),
                    "images": [b64],
                },
            ],
        }
        return payload

    def _post_generate(self, payload: Dict[str, Any]) -> str:
        # /api/chat supports vision images; /api/generate is text-only on many builds
        url = f"{self.cfg['base_url']}/api/chat"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = float(self.cfg.get("timeout_sec", 12.0))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"HTTP {e.code}: {detail}") from e

        message = body.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text") or ""))
                elif isinstance(part, str):
                    parts.append(part)
            joined = "".join(parts).strip()
            if joined:
                return joined
        # Some thinking models put the final JSON only in "thinking" if think wasn't disabled
        thinking = message.get("thinking")
        if isinstance(thinking, str) and thinking.strip():
            return thinking
        return str(body.get("response") or "")

    def _parse_response(self, raw: str) -> Tuple[str, float]:
        if not raw:
            return "", 0.0
        text = ""
        confidence = 0.0
        candidate = raw.strip()
        # Strip markdown fences if the model ignores format=json
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

        parsed = None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            match = _JSON_RE.search(raw)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = None

        if isinstance(parsed, dict):
            text = str(parsed.get("text") or "").strip()
            try:
                confidence = float(parsed.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
        else:
            # Unstructured reply → treat as unreadable / discard
            return "", 0.05

        confidence = max(0.0, min(1.0, confidence))
        # Model may return Latin garbage for blank tickers
        if not text or text.lower() in {"none", "n/a", "null", "unreadable", "illegible"}:
            return "", min(confidence, 0.05)
        return text, confidence


class SharedOllamaOcrService:
    """One shared Ollama OCR client for all channel monitors."""

    def __init__(self):
        self._client: Optional[OllamaVisionOcr] = None
        self._lock = threading.Lock()

    def ensure_loaded(self) -> OllamaVisionOcr:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                self._client = OllamaVisionOcr()
                if self._client.enabled:
                    ok = self._client.ping()
                    logging.info(
                        "Shared Ollama OCR %s (model=%s, url=%s)",
                        "ready" if ok else "unreachable — mid-conf OCR will be skipped",
                        self._client.cfg.get("model"),
                        self._client.cfg.get("base_url"),
                    )
            return self._client

    def get(self) -> Optional[OllamaVisionOcr]:
        return self._client
