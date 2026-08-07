"""
Hikvision-style NVR RTSP playback helpers.

Live:      /Streaming/Channels/101
Playback:  /Streaming/tracks/101?starttime=YYYYMMDDTHHMMSSZ&endtime=...
"""

from __future__ import annotations

import logging
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_CHANNELS_RE = re.compile(r"/Streaming/Channels/(\d+)", re.IGNORECASE)
_TRACKS_RE = re.compile(r"/Streaming/tracks?/(\d+)", re.IGNORECASE)

# Pakistan Standard Time (UTC+5). NVR wall clock is typically set to local time;
# Hikvision starttime/endtime should use that local clock, not UTC.
PKT = timezone(timedelta(hours=5))


def _as_pakistan_local(dt: datetime) -> datetime:
    """Treat naive datetimes as Pakistan local; convert aware ones to PKT."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=PKT)
    return dt.astimezone(PKT)


def format_hikvision_time(dt: datetime) -> str:
    """Compact time for Hikvision playback: YYYYMMDDTHHMMSSZ (Pakistan local)."""
    local = _as_pakistan_local(dt)
    # Device expects local wall-clock digits (Z suffix is conventional, not UTC here)
    return local.strftime("%Y%m%dT%H%M%SZ")


def live_rtsp_to_playback_url(
    live_url: str,
    start: datetime,
    end: datetime,
) -> str:
    """Convert a live Channels URL into a tracks playback URL with time range."""
    url = (live_url or "").strip()
    if not url:
        raise ValueError("Empty RTSP URL")

    parts = urlsplit(url)
    path = parts.path or ""

    match = _CHANNELS_RE.search(path)
    if match:
        path = _CHANNELS_RE.sub(rf"/Streaming/tracks/{match.group(1)}", path, count=1)
    else:
        track = _TRACKS_RE.search(path)
        if track:
            path = _TRACKS_RE.sub(
                rf"/Streaming/tracks/{track.group(1)}", path, count=1
            )
        else:
            raise ValueError(
                "URL must contain /Streaming/Channels/NNN or /Streaming/tracks/NNN"
            )

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["starttime"] = format_hikvision_time(start)
    query["endtime"] = format_hikvision_time(end)

    return urlunsplit(
        (parts.scheme, parts.netloc, path, urlencode(query), parts.fragment)
    )


def build_playback_stream_command(
    playback_url: str,
    duration: float,
) -> list:
    """
    ffmpeg command: NVR playback RTSP → fragmented MP4 on stdout (browser-playable).

    Video is copied when possible; audio is AAC for HTML5 <video> compatibility.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-fflags",
        "+genpts+discardcorrupt",
        "-i",
        playback_url,
        "-t",
        str(max(1.0, float(duration))),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "1",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        "pipe:1",
    ]


def open_playback_stream(playback_url: str, duration: float) -> subprocess.Popen:
    """Start ffmpeg piping fragmented MP4 to stdout."""
    command = build_playback_stream_command(playback_url, duration)
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )


def extract_playback_audio_clip(
    playback_url: str,
    output_path: Path,
    duration: float,
    sample_rate: int = 16000,
) -> Tuple[bool, str]:
    """
    Pull audio from an NVR playback RTSP URL into a WAV file via ffmpeg.

    Returns (ok, error_message).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove stale file so we never serve a partial previous clip
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-rtsp_transport",
        "tcp",
        "-fflags",
        "+genpts+discardcorrupt",
        "-i",
        playback_url,
        "-t",
        str(max(1.0, float(duration))),
        "-vn",
        "-map",
        "0:a:0?",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        str(output_path),
    ]

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            timeout=max(30.0, float(duration) + 25.0),
        )
        err = (proc.stderr or b"").decode(errors="ignore").strip()
        if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 44:
            if output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
            msg = err[-500:] if err else f"ffmpeg exit {proc.returncode}"
            logging.warning("NVR clip extract failed: %s", msg)
            return False, msg
        return True, ""
    except subprocess.TimeoutExpired:
        logging.warning("NVR clip extract timed out after %.0fs", duration)
        return False, "Timed out extracting clip from NVR"
    except FileNotFoundError:
        return False, "ffmpeg not found on PATH"
    except Exception as e:
        logging.warning("NVR clip extract error: %s", e)
        return False, str(e)


def new_clip_id() -> str:
    return str(uuid.uuid4())


def parse_clip_window(
    start_iso: str,
    duration_sec: float,
) -> Tuple[datetime, datetime, float]:
    """Parse start ISO + duration into (start, end, clamped_duration)."""
    raw = (start_iso or "").strip()
    if not raw:
        raise ValueError("start is required")

    # datetime-local: 2026-08-07T14:30
    start = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    duration = float(duration_sec)
    if duration < 1:
        raise ValueError("duration must be at least 1 second")
    if duration > 300:
        duration = 300.0
    end = start + timedelta(seconds=duration)
    return start, end, duration
