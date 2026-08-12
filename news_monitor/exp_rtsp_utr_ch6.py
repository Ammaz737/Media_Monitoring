"""
Ch6/7 NVR playtrack (default) → auto-find ticker → OCR every fit crop.
Skip: blur/interlace, exact same text. Scroll dedupe off unless --scroll-thr > 0.

  ..\\venv_opencv5\\Scripts\\python.exe exp_rtsp_utr_ch6.py --show
  ..\\venv_opencv5\\Scripts\\python.exe exp_rtsp_utr_ch6.py --channel channel_6 --start 2026-08-11T00:00 --duration 60
  ..\\venv_opencv5\\Scripts\\python.exe exp_rtsp_utr_ch6.py --channel channel_6 --db-regions --show
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from nvr_playback import live_rtsp_to_playback_url

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "data" / "news_monitor.db"
PLAYTRACK_CHANNELS = frozenset({"channel_6", "channel_7"})
FALLBACK_URLS = {
    "channel_6": "rtsp://admin:Admin123.@192.168.2.144:554/Streaming/Channels/901",
    "channel_7": "rtsp://admin:Admin123.@192.168.2.144:554/Streaming/Channels/1001",
}


def load_url(channel_id: str = "channel_6"):
    if not DB_PATH.exists():
        return FALLBACK_URLS.get(channel_id, FALLBACK_URLS["channel_6"])
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT rtsp_url FROM channels WHERE channel_name = ?",
            (channel_id,),
        ).fetchone()
    if row and row[0]:
        return row[0]
    return FALLBACK_URLS.get(channel_id, FALLBACK_URLS["channel_6"])


def load_region_frac(channel_id: str, key: str = "ticker"):
    """Fractional (x1,y1,x2,y2) from channels.text_regions, or None."""
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT text_regions FROM channels WHERE channel_name = ?",
            (channel_id,),
        ).fetchone()
    if not row or not row[0]:
        return None
    try:
        regions = json.loads(row[0])
        box = regions[key]["region"]
        return tuple(float(v) for v in box)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def frac_to_box(frame, frac: tuple[float, float, float, float]):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = frac
    return (
        int(x1 * w),
        int(y1 * h),
        int(x2 * w),
        int(y2 * h),
    )


def opencv5_filter(crop):
    # ponytail: identity — filter experiments later
    return crop


def _longest_run(mask: np.ndarray) -> tuple[int, int] | None:
    best = None
    i = 0
    n = len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        if best is None or (j - i) > (best[1] - best[0]):
            best = (i, j)
        i = j
    return best


def find_ticker_band(
    frame: np.ndarray,
    search_top: float = 0.72,
    search_bot: float = 0.99,
    min_h_px: int = 28,
    max_h_frac: float = 0.14,
    pad_y: int = 10,
    prev: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int] | None:
    """
    Find primary news ticker (x1,y1,x2,y2).

    Score = text-edge energy × color-bar coherence.
    Colored Urdu bars beat white English crawlers (high edge, low sat).
    """
    h, w = frame.shape[:2]
    y0 = int(search_top * h)
    y1 = int(search_bot * h)
    if y1 - y0 < min_h_px:
        return None

    roi = frame[y0:y1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    edge = np.mean(np.abs(gx), axis=1)
    sat_m = sat.mean(axis=1)
    sat_s = sat.std(axis=1)

    color = (sat_m / 255.0) * (1.0 - np.clip(sat_s / 80.0, 0, 1) * 0.5)
    score = edge * (0.20 + 1.60 * color)
    yy = np.linspace(search_top, search_bot, len(score))
    score = score * np.where(yy < 0.96, 1.0, 0.35)

    k = max(5, ((len(score) // 30) | 1))
    score = cv2.GaussianBlur(score.reshape(-1, 1), (1, k), 0).ravel()

    peak = float(score.max())
    if peak < 4.0:
        return None
    thr = max(0.42 * peak, 3.5)
    mask = score >= thr

    max_h = int(max_h_frac * h)
    candidates: list[tuple[float, int, int]] = []
    i = 0
    n = len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        a, b = i, j
        if (b - a) > max_h:
            peak_i = a + int(np.argmax(score[a:b]))
            half = max_h // 2
            a = max(0, peak_i - half)
            b = min(n, a + max_h)
            a = max(0, b - max_h)
        if (b - a) >= min_h_px:
            s = float(score[a:b].mean()) * (b - a)
            if prev is not None:
                y_mid = y0 + (a + b) / 2
                py_mid = (prev[1] + prev[3]) / 2
                if abs(y_mid - py_mid) < 50:
                    s *= 1.6
            candidates.append((s, a, b))
        i = j

    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, a, b = candidates[0]
    ya = max(0, y0 + a - pad_y)
    yb = min(h, y0 + b + pad_y)

    # Skip side weather / logo islands
    xa, xb = int(0.06 * w), int(0.88 * w)
    strip = gray[a:b]
    col_e = np.mean(np.abs(cv2.Sobel(strip, cv2.CV_32F, 1, 0, ksize=3)), axis=0)
    ck = max(15, ((len(col_e) // 30) | 1))
    col_e = cv2.GaussianBlur(col_e.reshape(1, -1), (ck, 1), 0).ravel()
    if float(col_e.max()) >= 4.0:
        crun = _longest_run(col_e >= max(0.22 * float(col_e.max()), 3.0))
        if crun is not None and (crun[1] - crun[0]) >= int(0.45 * w):
            xa = max(xa, crun[0])
            xb = min(xb, crun[1])

    if yb - ya < min_h_px or xb - xa < 80:
        return None
    return xa, ya, xb, yb


def crop_diff(a: np.ndarray | None, b: np.ndarray) -> float:
    if a is None:
        return 255.0
    aa = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY) if a.ndim == 3 else a
    bb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY) if b.ndim == 3 else b
    if aa.shape != bb.shape:
        bb = cv2.resize(bb, (aa.shape[1], aa.shape[0]), interpolation=cv2.INTER_AREA)
    return float(np.mean(cv2.absdiff(aa, bb)))


def sharpness(crop: np.ndarray) -> float:
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def interlaced_score(crop: np.ndarray) -> float:
    """Even/odd row combing — high on motion-blur / interlaced tickers."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    if g.shape[0] < 6:
        return 999.0
    even = g[0::2].astype(np.float32)
    odd = g[1::2].astype(np.float32)
    h = min(even.shape[0], odd.shape[0])
    return float(np.mean(np.abs(even[:h] - odd[:h])))


def norm_text(text: str) -> str:
    return "".join(text.split())


def urdu_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    u = sum(1 for c in chars if "\u0600" <= c <= "\u06FF")
    return u / len(chars)


def scroll_continuation(
    prev: np.ndarray | None,
    cur: np.ndarray,
    max_dx: int = 180,
    step: int = 6,
    thr: float = 28.0,
) -> tuple[bool, float]:
    """True if cur is mostly a horizontal scroll of prev (same crawl strip)."""
    if prev is None or prev.size == 0 or cur.size == 0:
        return False, 255.0
    ga = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY) if prev.ndim == 3 else prev
    gb = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY) if cur.ndim == 3 else cur
    h = min(ga.shape[0], gb.shape[0])
    ga, gb = ga[:h], gb[:h]
    tw = 320
    ga = cv2.resize(ga, (tw, h), interpolation=cv2.INTER_AREA)
    gb = cv2.resize(gb, (tw, h), interpolation=cv2.INTER_AREA)
    best = 255.0
    max_dx = min(max_dx, tw // 2)
    for dx in range(-max_dx, max_dx + 1, step):
        if dx >= 0:
            a, b = ga[:, dx:], gb[:, : tw - dx]
        else:
            a, b = ga[:, : tw + dx], gb[:, -dx:]
        if a.size == 0 or b.shape[1] < 40:
            continue
        d = float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))
        if d < best:
            best = d
    return best < thr, best


def color_bar_crop(
    crop: np.ndarray,
    min_sat: int = 40,
    min_col_frac: float = 0.35,
    min_width_frac: float = 0.40,
    pad_y: int = 10,
) -> tuple[np.ndarray, int, int] | None:
    """
    Keep solid ticker color bar (any hue); drop weather/logo islands.
    Not magenta-only — works for blue/red/green/pink channel skins.
    Returns (crop, x_off, x_end) or None.
    """
    if crop.size == 0:
        return None
    h, w = crop.shape[:2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    # Saturated brand bar (any hue) OR near-white crawler bar
    bar = ((sat >= min_sat) & (val >= 35)) | ((sat <= 40) & (val >= 180))

    row = bar.mean(axis=1).astype(np.float32)
    rk = max(3, ((h // 20) | 1))
    row = cv2.GaussianBlur(row.reshape(-1, 1), (1, rk), 0).ravel()
    rrun = _longest_run(row >= 0.30)
    if rrun is not None:
        ya = max(0, rrun[0] - pad_y)
        yb = min(h, rrun[1] + pad_y)
    else:
        ya, yb = 0, h

    col = bar[ya:yb].mean(axis=0).astype(np.float32)
    k = max(9, ((w // 40) | 1))
    col = cv2.GaussianBlur(col.reshape(1, -1), (k, 1), 0).ravel()
    run = _longest_run(col >= min_col_frac)
    if run is None:
        return None
    xa, xb = run
    xa = min(w - 1, max(0, xa + 2))
    xb = min(w, max(xa + 1, xb - 2))
    if (xb - xa) < int(min_width_frac * w):
        return None
    if yb - ya < 20:
        return None
    return crop[ya:yb, xa:xb].copy(), xa, xb


# back-compat alias
magenta_only = color_bar_crop


def crop_ok(
    crop: np.ndarray,
    box: tuple[int, int, int, int],
    frame_h: int,
    sharp: float,
    min_sharp: float,
    max_interlace: float,
    min_h: int,
) -> str | None:
    """Return skip reason or None if crop is fit to OCR/save."""
    x1, y1, x2, y2 = box
    h = y2 - y1
    if h < min_h:
        return "short"
    if y2 > int(0.93 * frame_h):
        return "lowband"  # bleeds into white English crawler
    if sharp < min_sharp:
        return "blur"
    if interlaced_score(crop) > max_interlace:
        return "interlace"
    return None


class AlwaysLatest:
    def __init__(self, url, reopen: bool = True):
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        self.url = url
        self.reopen = reopen
        self.ended = False
        self.cap = self._open()
        self._lock = threading.Lock()
        self._frame = None
        self._n = 0
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _open(self):
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP: {self.url}")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _reopen(self):
        if not self.reopen:
            with self._lock:
                self._frame = None
                self.ended = True
            self._stop.set()
            return
        try:
            self.cap.release()
        except Exception:
            pass
        time.sleep(0.5)
        try:
            self.cap = self._open()
            print("RTSP reopened", flush=True)
        except Exception as e:
            print(f"RTSP reopen fail: {e}", flush=True)
            time.sleep(1.0)

    def _loop(self):
        fails = 0
        while not self._stop.is_set():
            try:
                ok, frame = self.cap.read()
            except cv2.error as e:
                print(f"RTSP read error: {e}", flush=True)
                self._reopen()
                fails = 0
                continue
            if not ok or frame is None:
                fails += 1
                if fails >= 30:
                    self._reopen()
                    fails = 0
                else:
                    time.sleep(0.05)
                continue
            fails = 0
            with self._lock:
                self._frame = frame
                self._n += 1

    def latest(self):
        t_end = time.perf_counter() + 5.0
        while time.perf_counter() < t_end:
            with self._lock:
                if self._frame is not None:
                    return self._frame.copy(), self._n
            if self.ended:
                break
            time.sleep(0.01)
        return None, self._n

    def release(self):
        self._stop.set()
        try:
            self.cap.release()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(
        description="Auto ticker band + change/sharp gated UTRNet"
    )
    ap.add_argument("--poll", type=float, default=0.15, help="Seconds between band checks")
    ap.add_argument(
        "--min-ocr-interval",
        type=float,
        default=1.0,
        help="Min seconds between OCR calls",
    )
    ap.add_argument("--change", type=float, default=10.0, help="Min mean absdiff to OCR")
    ap.add_argument("--sharp", type=float, default=800.0, help="Min Laplacian variance")
    ap.add_argument("--max-interlace", type=float, default=16.0, help="Max even/odd row diff")
    ap.add_argument("--min-h", type=int, default=52, help="Min ticker band height px")
    ap.add_argument("--min-conf", type=float, default=0.94, help="Min UTRNet conf to save")
    ap.add_argument(
        "--scroll-thr",
        type=float,
        default=0.0,
        help="Skip OCR if scroll-align diff < this (0=off). Try 18–22 if needed.",
    )
    ap.add_argument("--min-urdu", type=float, default=0.45, help="Min Urdu-script char ratio")
    ap.add_argument("--frames", type=int, default=10, help="Fit OCR saves then exit (0=forever)")
    ap.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="OCR crop dir (default: data/exp_<channel>_crops).",
    )
    ap.add_argument("--no-save", action="store_true", help="Do not write crops")
    ap.add_argument(
        "--no-colorbar",
        action="store_true",
        help="Skip color-bar trim; use full band crop",
    )
    ap.add_argument(
        "--no-magenta",
        action="store_true",
        help="Alias for --no-colorbar",
    )
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--search-top", type=float, default=0.70)
    ap.add_argument(
        "--channel",
        default="channel_7",
        help="DB channel id (channel_6, channel_7, ...)",
    )
    ap.add_argument(
        "--start",
        default=None,
        help="Playtrack start ISO (channel_6/7). Default: now - duration.",
    )
    ap.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Playtrack window seconds for channel_6/7 (default 60)",
    )
    ap.add_argument(
        "--live",
        action="store_true",
        help="Force live RTSP even for channel_6/7",
    )
    ap.add_argument(
        "--db-regions",
        action="store_true",
        help="Use channels.text_regions from DB instead of auto band find",
    )
    ap.add_argument(
        "--region",
        default="ticker",
        help="DB text_regions key when --db-regions (default: ticker)",
    )
    args = ap.parse_args()

    live_url = load_url(args.channel)
    db_frac = None
    if args.db_regions:
        db_frac = load_region_frac(args.channel, args.region)
        if db_frac is None:
            raise SystemExit(
                f"no text_regions.{args.region} in DB for {args.channel}"
            )
    use_playtrack = args.channel in PLAYTRACK_CHANNELS and not args.live
    if use_playtrack:
        if args.start:
            start_dt = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
        else:
            start_dt = datetime.now() - timedelta(seconds=args.duration)
        end_dt = start_dt + timedelta(seconds=max(1.0, float(args.duration)))
        url = live_rtsp_to_playback_url(live_url, start_dt, end_dt)
    else:
        url = live_url
        start_dt = end_dt = None

    if args.no_save:
        save_dir = None
    elif args.save_dir is not None:
        save_dir = Path(args.save_dir) if str(args.save_dir) not in ("", "-") else None
    else:
        save_dir = HERE / "data" / f"exp_{args.channel}_crops"
    print(
        f"cv2={cv2.__version__}  channel={args.channel}  poll={args.poll}s  "
        f"min_ocr={args.min_ocr_interval}s  change>={args.change}  "
        f"sharp>={args.sharp}  conf>={args.min_conf}"
    )
    if db_frac is not None:
        print(f"band=db:{args.region} frac={db_frac}")
    else:
        print("band=auto")
    if use_playtrack:
        print(
            f"playtrack {start_dt.isoformat(timespec='seconds')} → "
            f"{end_dt.isoformat(timespec='seconds')} ({args.duration:.0f}s)"
        )
    print(f"url={url}")
    print(f"save_dir={save_dir or '(off)'}  colorbar={not (args.no_colorbar or args.no_magenta)}")

    predictor = None
    if not args.no_ocr:
        sys.path.insert(0, str(HERE))
        from utrnet_wrapper import UTRNetPredictor

        predictor = UTRNetPredictor()

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    stream = AlwaysLatest(url, reopen=not use_playtrack)
    last_crop = None
    last_ocr_crop = None
    last_box = None
    last_ocr_t = 0.0
    last_saved_text = ""
    n = 0
    skips = {
        "noband": 0,
        "blur": 0,
        "same": 0,
        "cooldown": 0,
        "same_text": 0,
        "dup_scroll": 0,
        "interlace": 0,
        "short": 0,
        "lowband": 0,
        "lowconf": 0,
        "nourdu": 0,
        "nobar": 0,
    }
    try:
        while args.frames == 0 or n < args.frames:
            time.sleep(args.poll)
            frame, drained = stream.latest()
            if frame is None:
                if stream.ended:
                    print("playtrack ended", flush=True)
                    break
                continue

            t0 = time.perf_counter()
            if db_frac is not None:
                box = frac_to_box(frame, db_frac)
                x1, y1, x2, y2 = box
                if x2 <= x1 or y2 <= y1:
                    skips["noband"] += 1
                    continue
                last_box = box
                raw = frame[y1:y2, x1:x2].copy()
            else:
                box = find_ticker_band(frame, search_top=args.search_top, prev=last_box)
                if box is None:
                    skips["noband"] += 1
                    if args.show:
                        vis = frame.copy()
                        cv2.putText(
                            vis, "no band", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
                        )
                        cv2.imshow("frame", cv2.resize(vis, (960, 540)))
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    continue

                x1, y1, x2, y2 = box
                last_box = box
                # Extra vertical pad so Urdu nuqtas / descenders not clipped
                # ponytail: skip pad for DB boxes — Settings already drawn exact
                vpad = 12
                ya = max(0, y1 - vpad)
                yb = min(frame.shape[0], y2 + vpad)
                raw = frame[ya:yb, x1:x2].copy()
                y1, y2 = ya, yb
            mx_off = 0
            use_bar = not (args.no_colorbar or args.no_magenta)
            if use_bar:
                trimmed = color_bar_crop(raw)
                if trimmed is None:
                    # Fall back to full band — don't drop the ticker
                    crop = opencv5_filter(raw)
                    skips["nobar"] += 1
                else:
                    crop, mx_off, _ = trimmed
                    crop = opencv5_filter(crop)
            else:
                crop = opencv5_filter(raw)
            sharp = sharpness(crop)
            diff = crop_diff(last_crop, crop)
            ilace = interlaced_score(crop)

            if args.show:
                vis = frame.copy()
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                if use_bar and mx_off:
                    cv2.rectangle(
                        vis,
                        (x1 + mx_off, y1),
                        (x1 + mx_off + crop.shape[1], y2),
                        (255, 0, 255),
                        2,
                    )
                cv2.putText(
                    vis,
                    f"diff={diff:.1f} sharp={sharp:.0f} ilace={ilace:.1f}",
                    (x1, max(30, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("ticker", crop)
                cv2.imshow("frame", cv2.resize(vis, (960, 540)))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.perf_counter()
            if now - last_ocr_t < args.min_ocr_interval:
                skips["cooldown"] += 1
                continue
            if diff < args.change:
                skips["same"] += 1
                continue

            # Fit checks use magenta crop size; box y still from band
            reason = crop_ok(
                crop,
                (x1 + mx_off, y1, x1 + mx_off + crop.shape[1], y2),
                frame.shape[0],
                sharp,
                args.sharp,
                args.max_interlace,
                args.min_h,
            )
            if reason:
                skips[reason] = skips.get(reason, 0) + 1
                continue

            # Optional scroll dedupe (off by default — thr=0)
            if args.scroll_thr > 0:
                is_scroll, scroll_d = scroll_continuation(
                    last_ocr_crop, crop, thr=args.scroll_thr
                )
                if is_scroll:
                    last_crop = crop.copy()
                    last_ocr_crop = crop.copy()
                    last_ocr_t = now
                    skips["dup_scroll"] += 1
                    continue
            else:
                scroll_d = 255.0

            last_crop = crop.copy()
            last_ocr_t = now
            find_ms = (time.perf_counter() - t0) * 1000

            if predictor is None:
                last_ocr_crop = crop.copy()
                if save_dir:
                    path = save_dir / f"{n:04d}_ticker.png"
                    cv2.imwrite(str(path), crop)
                    print(
                        f"[{n}] saved={path.name} band={crop.shape[1]}x{crop.shape[0]} @{y1} "
                        f"find={find_ms:.0f}ms diff={diff:.1f} sharp={sharp:.0f}"
                    )
                n += 1
                continue

            text, conf = predictor.predict_single(crop)
            if conf < args.min_conf:
                skips["lowconf"] += 1
                continue
            if urdu_ratio(text) < args.min_urdu:
                skips["nourdu"] += 1
                continue

            # Only skip exact same string (paused ticker)
            nt = norm_text(text)
            if nt and nt == last_saved_text:
                last_ocr_crop = crop.copy()
                skips["same_text"] += 1
                continue
            if nt:
                last_saved_text = nt

            last_ocr_crop = crop.copy()
            saved = ""
            if save_dir:
                stem = f"{n:04d}_{conf:.2f}_ticker"
                path = save_dir / f"{stem}.png"
                cv2.imwrite(str(path), crop)
                (save_dir / f"{stem}.txt").write_text(
                    f"confidence={conf:.4f}\n"
                    f"sharp={sharp:.1f}\ninterlace={ilace:.2f}\n"
                    f"scroll_diff={scroll_d:.1f}\n"
                    f"box={x1},{y1},{x2},{y2}\nbar_x={mx_off}\ntext={text}\n",
                    encoding="utf-8",
                )
                saved = f" saved={path.name}"

            line = (
                f"[{n}] conf={conf:.3f} find={find_ms:.0f}ms "
                f"diff={diff:.1f} sharp={sharp:.0f} ilace={ilace:.1f} "
                f"scroll={scroll_d:.1f} mag={crop.shape[1]}x{crop.shape[0]}"
                f"{saved}  {text!r}"
            )
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("utf-8", "replace").decode("ascii", "replace"))
            n += 1
    finally:
        print(f"skips={skips}")
        stream.release()
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
