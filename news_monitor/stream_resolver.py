"""
Resolve dashboard stream URLs (RTSP, HTTP, YouTube) to something OpenCV/ffmpeg can read.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional, Tuple

import cv2
import numpy as np


def is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u or "youtube-nocookie.com" in u


def resolve_stream_url(url: str) -> Tuple[str, str | None]:
    """
    Returns (resolved_url, error_message).
    error_message is None on success.
    """
    url = (url or "").strip()
    if not url:
        return url, "Stream URL is empty."

    if is_youtube_url(url):
        return _resolve_youtube(url)

    return url, None


def _resolve_youtube(url: str) -> Tuple[str, str | None]:
    try:
        import yt_dlp
    except ImportError:
        return (
            url,
            "YouTube links require yt-dlp. Run: pip install yt-dlp — then restart Flask.",
        )

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            # Prefer HLS for live streams (more stable with ffmpeg than single MP4 chunk URLs)
            "format": (
                "best[height<=720][protocol^=m3u8]/"
                "best[height<=720]/best[height<=1080]/best"
            ),
            "socket_timeout": 30,
            "nocheckcertificate": True,
            "live_from_start": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return url, "Could not read YouTube stream info."

            manifest = info.get("manifest_url") or info.get("url")
            if manifest and "m3u8" in manifest:
                logging.info("Resolved YouTube HLS manifest")
                return manifest, None

            direct = info.get("url")
            if direct:
                logging.info("Resolved YouTube stream URL")
                return direct, None

            for fmt in reversed(info.get("formats") or []):
                fmt_url = fmt.get("url")
                if not fmt_url or fmt.get("vcodec") in (None, "none"):
                    continue
                if fmt.get("protocol") in ("m3u8", "m3u8_native") or "m3u8" in fmt_url:
                    logging.info("Resolved YouTube HLS from format list")
                    return fmt_url, None
                logging.info("Resolved YouTube stream from format list")
                return fmt_url, None

        return url, "Could not extract a playable URL from this YouTube link."
    except Exception as e:
        logging.error(f"YouTube resolve failed: {e}")
        return url, f"YouTube error: {e}"


def probe_video_stream(url: str, timeout_sec: float = 12.0) -> Tuple[bool, str | None]:
    """Try to open URL and read at least one frame."""
    cap = None
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return False, (
                "Cannot open video stream. "
                "Use RTSP (rtsp://...) or install yt-dlp for YouTube: pip install yt-dlp"
            )

        import time

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                return True, None
            time.sleep(0.4)

        return (
            False,
            "Stream connected but no video frames received. Check if the link is live.",
        )
    except Exception as e:
        return False, str(e)
    finally:
        if cap is not None:
            cap.release()


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


class FfmpegFrameReader:
    """Read BGR frames via ffmpeg pipe (more reliable for YouTube HLS than OpenCV alone)."""

    def __init__(self, url: str, width: int = 1280, height: int = 720):
        self.url = url
        self.width = width
        self.height = height
        self._proc: Optional[subprocess.Popen] = None
        self._frame_bytes = width * height * 3

    def open(self) -> None:
        self.release()
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-i",
            self.url,
            "-an",
            "-sn",
            "-vf",
            f"scale={self.width}:{self.height}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=self._frame_bytes * 4,
        )

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._proc or not self._proc.stdout:
            return False, None
        raw = self._proc.stdout.read(self._frame_bytes)
        if not raw or len(raw) < self._frame_bytes:
            return False, None
        frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))
        return True, frame.copy()

    def release(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
