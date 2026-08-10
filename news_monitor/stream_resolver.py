"""
Resolve dashboard stream URLs (RTSP, HTTP, YouTube) to something OpenCV/ffmpeg can read.
"""

from __future__ import annotations

import logging
import re
import shutil
import ssl
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import cv2
import numpy as np

# Default when URL has no quality/height/vq hint
_DEFAULT_YT_HEIGHT = 720
_QUALITY_QUERY_KEYS = ("quality", "height", "vq", "res")

# Python 3.12 removed ssl.wrap_socket; older eventlet/curl_cffi still expect it.
if not hasattr(ssl, "wrap_socket"):
    def _wrap_socket(sock, keyfile=None, certfile=None, server_side=False,
                     cert_reqs=ssl.CERT_NONE, ssl_version=None, ca_certs=None,
                     do_handshake_on_connect=True, suppress_ragged_eofs=True,
                     ciphers=None):
        ctx = ssl.SSLContext(ssl_version or ssl.PROTOCOL_TLS_CLIENT)
        if cert_reqs is not None:
            ctx.verify_mode = cert_reqs
        if ca_certs:
            ctx.load_verify_locations(ca_certs)
        if certfile:
            ctx.load_cert_chain(certfile, keyfile)
        if ciphers:
            ctx.set_ciphers(ciphers)
        return ctx.wrap_socket(
            sock,
            server_side=server_side,
            do_handshake_on_connect=do_handshake_on_connect,
            suppress_ragged_eofs=suppress_ragged_eofs,
        )

    ssl.wrap_socket = _wrap_socket  # type: ignore[attr-defined]


def is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u or "youtube-nocookie.com" in u


def parse_youtube_preferred_height(url: str) -> Tuple[str, int]:
    """
    Read optional stream height from the watch URL query, then strip those keys.

    Supported examples (app-only; YouTube ignores them):
      .../watch?v=ID&quality=720
      .../watch?v=ID&quality=720p
      .../watch?v=ID&height=1080
      .../watch?v=ID&vq=hd720
      .../watch?v=ID&res=480
    """
    url = (url or "").strip()
    if not url or not is_youtube_url(url):
        return url, _DEFAULT_YT_HEIGHT

    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    raw = None
    for key in _QUALITY_QUERY_KEYS:
        if key in qs and qs[key]:
            raw = (qs[key][0] or "").strip()
            break

    height = _DEFAULT_YT_HEIGHT
    if raw:
        parsed_h = _parse_height_token(raw)
        if parsed_h:
            height = parsed_h

    for key in _QUALITY_QUERY_KEYS:
        qs.pop(key, None)

    clean_query = urlencode(
        [(k, v) for k, values in qs.items() for v in values],
        doseq=False,
    )
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, height


def _parse_height_token(token: str) -> Optional[int]:
    """Map '720', '720p', 'hd720', 'fullhd', '4k' → pixel height."""
    t = (token or "").strip().lower().replace(" ", "")
    aliases = {
        "144": 144,
        "240": 240,
        "360": 360,
        "480": 480,
        "720": 720,
        "1080": 1080,
        "1440": 1440,
        "2160": 2160,
        "4k": 2160,
        "uhd": 2160,
        "fullhd": 1080,
        "fhd": 1080,
        "hd": 720,
        "sd": 480,
        "hd720": 720,
        "hd1080": 1080,
        "highres": 1080,
    }
    if t in aliases:
        return aliases[t]
    m = re.search(r"(\d{3,4})", t)
    if not m:
        return None
    h = int(m.group(1))
    if 144 <= h <= 2160:
        return h
    return None


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


def _youtube_auth_opts() -> dict:
    """Optional cookies so private/members YouTube lives can resolve."""
    opts: dict = {}
    try:
        from config import YOUTUBE_COOKIES_FILE, YOUTUBE_COOKIES_FROM_BROWSER
    except Exception:
        return opts

    cookie_file = Path(YOUTUBE_COOKIES_FILE) if YOUTUBE_COOKIES_FILE else None
    if cookie_file and cookie_file.is_file() and cookie_file.stat().st_size > 0:
        opts["cookiefile"] = str(cookie_file)
        logging.info("YouTube: using cookies file %s", cookie_file)
        return opts

    browser = (YOUTUBE_COOKIES_FROM_BROWSER or "").strip().lower()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
        logging.info("YouTube: using cookies from browser=%s", browser)
    return opts


def _friendly_youtube_error(err: Exception | str) -> str:
    msg = str(err)
    low = msg.lower()
    if "private video" in low:
        return (
            "This YouTube video is PRIVATE. Open it while logged in, export cookies to "
            "news_monitor/data/youtube_cookies.txt, then restart Flask — "
            "or use a public Live URL / RTSP."
        )
    if "members-only" in low or "join this channel" in low:
        return (
            "Members-only YouTube stream. Export logged-in cookies to "
            "news_monitor/data/youtube_cookies.txt and restart Flask."
        )
    if "sign in" in low and "age" in low:
        return (
            "Age-restricted YouTube video. Export cookies from a signed-in browser "
            "to news_monitor/data/youtube_cookies.txt."
        )
    if "incomplete youtube id" in low or "truncated" in low:
        return "Invalid/truncated YouTube ID. Copy the full watch URL from the browser."
    if "no video formats found" in low:
        return (
            "YouTube blocked format list for this video (region/login/age). "
            "Try cookies file, another live link, or RTSP."
        )
    if "could not copy" in low and "cookie" in low:
        return (
            "Could not read browser cookies (Chrome/Edge lock the DB). "
            "Fully close the browser, or export cookies to "
            "news_monitor/data/youtube_cookies.txt."
        )
    return f"YouTube error: {msg}"


def _resolve_youtube(url: str) -> Tuple[str, str | None]:
    try:
        import yt_dlp
    except ImportError:
        return (
            url,
            "YouTube links require yt-dlp. Run: pip install yt-dlp — then restart Flask.",
        )

    clean_url, preferred_height = parse_youtube_preferred_height(url)

    # Some live channels only expose formats via android/ios clients.
    # Try several client stacks; first success wins.
    client_stacks = (
        ["android", "web"],
        ["ios", "web"],
        ["mweb", "web"],
        ["tv_embedded", "web"],
        ["web"],
    )
    auth_opts = _youtube_auth_opts()

    last_error: Exception | None = None
    for clients in client_stacks:
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                # Don't force a narrow format — pick after extract from format list
                "format": "best/bestvideo+bestaudio/best",
                "socket_timeout": 30,
                "nocheckcertificate": True,
                "live_from_start": False,
                "extractor_args": {
                    "youtube": {
                        "player_client": clients,
                    }
                },
                **auth_opts,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
            if not info:
                continue

            live_status = info.get("live_status")
            is_live = bool(info.get("is_live")) or live_status == "is_live"

            # Prefer HLS for live (stable with ffmpeg); fall back to any playable URL
            playable = _pick_youtube_playable_url(
                info, prefer_hls=is_live, preferred_height=preferred_height
            )
            if playable:
                kind = "HLS" if "m3u8" in playable else "direct"
                logging.info(
                    "Resolved YouTube (%s, clients=%s, live=%s, height~%sp)",
                    kind,
                    "+".join(clients),
                    is_live,
                    preferred_height,
                )
                return playable, None

            if live_status == "was_live":
                return (
                    url,
                    "This YouTube stream ended (was live). Open the channel's current Live URL.",
                )
            if live_status == "is_upcoming":
                return url, "This YouTube live has not started yet."

        except Exception as e:
            last_error = e
            logging.warning("YouTube resolve attempt failed (%s): %s", "+".join(clients), e)
            # Private/members won't succeed with other clients without auth
            if "private video" in str(e).lower() or "members-only" in str(e).lower():
                break
            continue

    if last_error:
        return url, _friendly_youtube_error(last_error)

    return url, "Could not extract a playable URL from this YouTube link."


def _pick_youtube_playable_url(
    info: dict,
    prefer_hls: bool = True,
    preferred_height: int = _DEFAULT_YT_HEIGHT,
) -> str | None:
    """Choose the best ffmpeg-friendly URL from yt-dlp info."""
    formats = list(info.get("formats") or [])
    target_h = int(preferred_height or _DEFAULT_YT_HEIGHT)

    def is_hls(fmt: dict) -> bool:
        proto = (fmt.get("protocol") or "").lower()
        u = fmt.get("url") or ""
        return "m3u8" in proto or "m3u8" in u

    def has_video(fmt: dict) -> bool:
        return fmt.get("vcodec") not in (None, "none")

    # Top-level HLS master manifests encode multiple renditions; skip when the
    # caller asked for a specific height so we can pick a concrete stream.
    if prefer_hls and target_h == _DEFAULT_YT_HEIGHT:
        for key in ("manifest_url", "url"):
            candidate = info.get(key)
            if candidate and "m3u8" in candidate:
                return candidate

    ranked = []
    for fmt in formats:
        u = fmt.get("url")
        if not u or not has_video(fmt):
            continue
        height = fmt.get("height") or 0
        # Prefer formats closest to the URL quality hint (default 720p)
        height_score = -abs(height - target_h) if height else -9999
        hls_score = 100 if is_hls(fmt) else 0
        if prefer_hls and not is_hls(fmt):
            hls_score -= 50
        ranked.append((hls_score, height_score, height, u))

    if ranked:
        ranked.sort(reverse=True)
        return ranked[0][3]

    # Last resort: any top-level URL
    return info.get("manifest_url") or info.get("url")


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


def grab_stream_frame(
    url: str,
    timeout_sec: float = 20.0,
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Grab one BGR frame from RTSP/HTTP/YouTube.
    Returns (frame, error_message). YouTube uses ffmpeg when available.
    """
    import time as _time

    url = (url or "").strip()
    if not url:
        return None, "Stream URL is empty."

    try:
        resolved, err = resolve_stream_url(url)
        if err:
            return None, err
        play_url = resolved
    except Exception as e:
        return None, str(e)

    youtube = is_youtube_url(url)
    deadline = _time.time() + (timeout_sec if youtube else min(timeout_sec, 12.0))

    if youtube and ffmpeg_available():
        reader = FfmpegFrameReader(play_url)
        try:
            reader.open()
            best = None
            while _time.time() < deadline:
                ret, frame = reader.read()
                if ret and frame is not None and getattr(frame, "size", 0) > 0:
                    best = frame
                    # One more read so HLS decoder settles on a real frame
                    ret2, frame2 = reader.read()
                    if ret2 and frame2 is not None and getattr(frame2, "size", 0) > 0:
                        best = frame2
                    break
                _time.sleep(0.05)
            if best is not None:
                return best, None
            return None, (
                "YouTube stream opened but no video frames yet. "
                "Try again in a few seconds."
            )
        except Exception as e:
            logging.warning("ffmpeg YouTube snapshot failed: %s", e)
        finally:
            reader.release()

    cap = cv2.VideoCapture(play_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap.release()
        return None, "Cannot open video stream for snapshot."
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        best = None
        for i in range(15 if youtube else 10):
            if _time.time() > deadline:
                break
            ret, frame = cap.read()
            if ret and frame is not None and getattr(frame, "size", 0) > 0:
                best = frame
                if i >= (3 if youtube else 2):
                    break
            _time.sleep(0.12 if youtube else 0.1)
        if best is not None:
            return best, None
        return None, "Stream connected but no frames received for snapshot."
    finally:
        cap.release()


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
