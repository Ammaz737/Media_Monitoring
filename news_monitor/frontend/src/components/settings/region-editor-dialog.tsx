"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  Crosshair,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Scan,
} from "lucide-react";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { TextRegionMap } from "@/lib/types";
import { api } from "@/lib/api";

export type RtspRegionKey = "ticker" | "headline" | "side_text";
export type YoutubeRegionKey = "youtube_ticker" | "youtube_top_bar";
export type RegionKey = RtspRegionKey | YoutubeRegionKey;

type RegionMeta = {
  label: string;
  hint: string;
  color: string;
  ring: string;
  fill: string;
};

const RTSP_REGION_META: Record<RtspRegionKey, RegionMeta> = {
  ticker: {
    label: "Ticker",
    hint: "Bottom news crawl",
    color: "#f59e0b",
    ring: "ring-amber-400",
    fill: "bg-amber-400/20 border-amber-400",
  },
  headline: {
    label: "Headline",
    hint: "Top breaking band",
    color: "#38bdf8",
    ring: "ring-sky-400",
    fill: "bg-sky-400/20 border-sky-400",
  },
  side_text: {
    label: "Side",
    hint: "Right info panel",
    color: "#34d399",
    ring: "ring-emerald-400",
    fill: "bg-emerald-400/20 border-emerald-400",
  },
};

const YOUTUBE_REGION_META: Record<YoutubeRegionKey, RegionMeta> = {
  youtube_ticker: {
    label: "Ticker",
    hint: "Bottom YouTube crawl",
    color: "#f59e0b",
    ring: "ring-amber-400",
    fill: "bg-amber-400/20 border-amber-400",
  },
  youtube_top_bar: {
    label: "Top bar",
    hint: "Breaking / headline strip",
    color: "#38bdf8",
    ring: "ring-sky-400",
    fill: "bg-sky-400/20 border-sky-400",
  },
};

const DEFAULT_RTSP_REGIONS: TextRegionMap = {
  ticker: {
    name: "Bottom Ticker",
    region: [0, 0.8, 1.0, 1.0],
    priority: "high",
    min_confidence: 0.7,
  },
  headline: {
    name: "Headline Area",
    region: [0, 0, 1.0, 0.3],
    priority: "medium",
    min_confidence: 0.6,
  },
  side_text: {
    name: "Side Information",
    region: [0.7, 0.3, 1.0, 0.7],
    priority: "low",
    min_confidence: 0.5,
  },
};

const DEFAULT_YOUTUBE_REGIONS: TextRegionMap = {
  youtube_ticker: {
    name: "Bottom Ticker",
    region: [0.0, 0.86, 1.0, 0.99],
    priority: "high",
    min_confidence: 0.72,
  },
  youtube_top_bar: {
    name: "Top Breaking Bar",
    region: [0.0, 0.0, 1.0, 0.11],
    priority: "high",
    min_confidence: 0.72,
  },
};

/** @deprecated use DEFAULT_RTSP_REGIONS */
const DEFAULT_REGIONS = DEFAULT_RTSP_REGIONS;

type DragMode =
  | { type: "move"; key: RegionKey; ox: number; oy: number; start: number[] }
  | {
      type: "resize";
      key: RegionKey;
      handle: string;
      start: number[];
      ox: number;
      oy: number;
    };

function clamp(n: number, min = 0, max = 1) {
  return Math.max(min, Math.min(max, n));
}

function normalizeBox(r: number[]): [number, number, number, number] {
  let [x1, y1, x2, y2] = r.map(Number);
  if (x2 < x1) [x1, x2] = [x2, x1];
  if (y2 < y1) [y1, y2] = [y2, y1];
  x1 = clamp(x1);
  y1 = clamp(y1);
  x2 = clamp(x2);
  y2 = clamp(y2);
  if (x2 - x1 < 0.03) x2 = Math.min(1, x1 + 0.03);
  if (y2 - y1 < 0.03) y2 = Math.min(1, y1 + 0.03);
  return [
    Math.round(x1 * 1000) / 1000,
    Math.round(y1 * 1000) / 1000,
    Math.round(x2 * 1000) / 1000,
    Math.round(y2 * 1000) / 1000,
  ];
}

export function isYoutubeStreamUrl(url?: string | null): boolean {
  const u = (url || "").toLowerCase();
  return (
    u.includes("youtube.com") ||
    u.includes("youtu.be") ||
    u.includes("youtube-nocookie.com") ||
    u.startsWith("yt:")
  );
}

function ensureRegionMap(
  input: TextRegionMap | null | undefined,
  defaults: TextRegionMap
): TextRegionMap {
  const keys = Object.keys(defaults);
  const out: TextRegionMap = {};
  for (const key of keys) {
    const src = input?.[key] ?? defaults[key];
    out[key] = {
      ...defaults[key],
      ...src,
      region: normalizeBox(src.region ?? defaults[key].region),
    };
  }
  return out;
}

/** Map legacy RTSP-style boxes onto YouTube keys when re-opening editor. */
function coerceYoutubeRegions(input?: TextRegionMap | null): TextRegionMap {
  if (!input) return ensureRegionMap(null, DEFAULT_YOUTUBE_REGIONS);
  const hasYt = Object.keys(input).some((k) => k.startsWith("youtube_"));
  if (hasYt) return ensureRegionMap(input, DEFAULT_YOUTUBE_REGIONS);

  const mapped: TextRegionMap = { ...DEFAULT_YOUTUBE_REGIONS };
  if (input.ticker?.region) {
    mapped.youtube_ticker = {
      ...DEFAULT_YOUTUBE_REGIONS.youtube_ticker,
      ...input.ticker,
      name: input.ticker.name || "Bottom Ticker",
      region: normalizeBox(input.ticker.region),
    };
  }
  if (input.headline?.region) {
    mapped.youtube_top_bar = {
      ...DEFAULT_YOUTUBE_REGIONS.youtube_top_bar,
      ...input.headline,
      name: input.headline.name || "Top Breaking Bar",
      region: normalizeBox(input.headline.region),
    };
  }
  return ensureRegionMap(mapped, DEFAULT_YOUTUBE_REGIONS);
}

interface RegionEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channelId: string;
  channelName: string;
  streamUrl?: string;
  initialRegions?: TextRegionMap | null;
  onSaved: (channels: Record<string, unknown>) => void;
}

export function RegionEditorDialog({
  open,
  onOpenChange,
  channelId,
  channelName,
  streamUrl,
  initialRegions,
  onSaved,
}: RegionEditorDialogProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const youtube = isYoutubeStreamUrl(streamUrl);
  const defaults = youtube ? DEFAULT_YOUTUBE_REGIONS : DEFAULT_RTSP_REGIONS;
  const regionMeta = youtube ? YOUTUBE_REGION_META : RTSP_REGION_META;
  const regionKeys = useMemo(
    () => Object.keys(defaults) as RegionKey[],
    [defaults]
  );

  const [regions, setRegions] = useState<TextRegionMap>(() =>
    youtube
      ? coerceYoutubeRegions(initialRegions)
      : ensureRegionMap(initialRegions, DEFAULT_RTSP_REGIONS)
  );
  const [active, setActive] = useState<RegionKey>(regionKeys[0]);
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null);
  const [snapshotMeta, setSnapshotMeta] = useState<{
    w: number;
    h: number;
    source: string;
  } | null>(null);
  const [loadingShot, setLoadingShot] = useState(false);
  const [shotError, setShotError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const dragRef = useRef<DragMode | null>(null);

  const loadSnapshot = useCallback(async () => {
    setLoadingShot(true);
    setShotError(null);
    try {
      const shot = await api.getChannelSnapshot(channelId);
      setSnapshotUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return shot.url;
      });
      setSnapshotMeta({
        w: shot.width,
        h: shot.height,
        source: shot.source,
      });
    } catch (e) {
      setShotError(e instanceof Error ? e.message : "Failed to load frame");
    } finally {
      setLoadingShot(false);
    }
  }, [channelId]);

  useEffect(() => {
    if (!open) return;
    const next = youtube
      ? coerceYoutubeRegions(initialRegions)
      : ensureRegionMap(initialRegions, DEFAULT_RTSP_REGIONS);
    setRegions(next);
    setActive((Object.keys(next)[0] as RegionKey) || regionKeys[0]);
    setStatus(null);
    void loadSnapshot();
    return () => {
      setSnapshotUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [open, channelId, initialRegions, loadSnapshot, youtube, regionKeys]);

  const pointerToFrac = (clientX: number, clientY: number) => {
    const el = stageRef.current;
    if (!el) return { x: 0, y: 0 };
    const rect = el.getBoundingClientRect();
    return {
      x: clamp((clientX - rect.left) / rect.width),
      y: clamp((clientY - rect.top) / rect.height),
    };
  };

  const updateRegionBox = (key: RegionKey, box: number[]) => {
    setRegions((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        region: normalizeBox(box),
      },
    }));
  };

  const onPointerMove = useCallback((e: PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const { x, y } = (() => {
      const el = stageRef.current;
      if (!el) return { x: 0, y: 0 };
      const rect = el.getBoundingClientRect();
      return {
        x: clamp((e.clientX - rect.left) / rect.width),
        y: clamp((e.clientY - rect.top) / rect.height),
      };
    })();

    const [sx1, sy1, sx2, sy2] = drag.start;

    if (drag.type === "move") {
      const w = sx2 - sx1;
      const h = sy2 - sy1;
      let nx1 = x - drag.ox;
      let ny1 = y - drag.oy;
      nx1 = clamp(nx1, 0, 1 - w);
      ny1 = clamp(ny1, 0, 1 - h);
      updateRegionBox(drag.key, [nx1, ny1, nx1 + w, ny1 + h]);
      return;
    }

    let x1 = sx1;
    let y1 = sy1;
    let x2 = sx2;
    let y2 = sy2;
    const h = drag.handle;
    if (h.includes("w")) x1 = x;
    if (h.includes("e")) x2 = x;
    if (h.includes("n")) y1 = y;
    if (h.includes("s")) y2 = y;
    updateRegionBox(drag.key, [x1, y1, x2, y2]);
  }, []);

  const endDrag = useCallback(() => {
    dragRef.current = null;
  }, []);

  useEffect(() => {
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", endDrag);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", endDrag);
      window.removeEventListener("pointercancel", endDrag);
    };
  }, [onPointerMove, endDrag]);

  const startMove = (key: RegionKey, e: ReactPointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActive(key);
    const { x, y } = pointerToFrac(e.clientX, e.clientY);
    const box = regions[key].region;
    dragRef.current = {
      type: "move",
      key,
      ox: x - box[0],
      oy: y - box[1],
      start: [...box],
    };
  };

  const startResize = (
    key: RegionKey,
    handle: string,
    e: ReactPointerEvent
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setActive(key);
    const { x, y } = pointerToFrac(e.clientX, e.clientY);
    dragRef.current = {
      type: "resize",
      key,
      handle,
      start: [...regions[key].region],
      ox: x,
      oy: y,
    };
  };

  const setCoord = (idx: number, value: string) => {
    const n = Number(value);
    if (Number.isNaN(n)) return;
    const box = [...regions[active].region];
    box[idx] = n;
    updateRegionBox(active, box);
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      // Persist only the keys for this stream type (drops leftover RTSP keys on YT)
      const payload: TextRegionMap = {};
      for (const key of regionKeys) {
        if (regions[key]) payload[key] = regions[key];
      }
      const res = await api.updateChannelRegions(channelId, payload);
      onSaved(res.channels as Record<string, unknown>);
      setStatus("Regions saved — OCR will use these boxes immediately");
      onOpenChange(false);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setRegions(ensureRegionMap(null, defaults));
    setActive(regionKeys[0]);
    setStatus(
      youtube
        ? "Reset to YouTube defaults (not saved yet)"
        : "Reset to defaults (not saved yet)"
    );
  };

  const activeDef = regions[active];
  const meta = regionMeta[active as keyof typeof regionMeta];

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      className="max-w-[960px] overflow-hidden bg-transparent p-0 shadow-none [&_button.absolute]:text-slate-400 [&_button.absolute]:hover:bg-white/10 [&_button.absolute]:hover:text-white"
    >
      <div className="relative overflow-hidden rounded-2xl bg-[#0b1220] text-slate-100">
        {/* Atmosphere */}
        <div
          className="pointer-events-none absolute inset-0 opacity-80"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 20% 0%, rgba(56,189,248,0.12), transparent 55%), radial-gradient(ellipse 60% 40% at 90% 100%, rgba(245,158,11,0.1), transparent 50%)",
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
          }}
        />

        <div className="relative border-b border-white/10 px-6 pb-4 pt-6 pe-14">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-300/80">
                <Scan className="h-3.5 w-3.5" />
                OCR crop studio
                {youtube && (
                  <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-rose-300">
                    YouTube
                  </span>
                )}
              </div>
              <h3 className="text-xl font-semibold tracking-tight text-white">
                {channelName}
              </h3>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                {youtube
                  ? "Drag the ticker and top-bar boxes on the YouTube frame. Boxes are saved per channel."
                  : "Drag boxes on the frame to set ticker, headline, and side OCR zones. Boxes are saved per channel."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                onClick={() => void loadSnapshot()}
                disabled={loadingShot}
              >
                {loadingShot ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh frame
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                onClick={handleReset}
              >
                <RotateCcw className="h-4 w-4" />
                Defaults
              </Button>
            </div>
          </div>
        </div>

        <div className="relative grid gap-5 p-5 lg:grid-cols-[1fr_240px]">
          {/* Stage */}
          <div className="space-y-3">
            <div className="overflow-hidden rounded-xl border border-white/10 bg-[#05080f] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04),0_20px_50px_rgba(0,0,0,0.45)]">
              <div
                ref={stageRef}
                className="relative w-full touch-none select-none"
                style={{ minHeight: snapshotUrl ? undefined : 280 }}
              >
              {/* Scanline + grid */}
              <div
                className="pointer-events-none absolute inset-0 z-[1] opacity-[0.07]"
                style={{
                  backgroundImage:
                    "linear-gradient(rgba(148,163,184,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.35) 1px, transparent 1px)",
                  backgroundSize: "40px 40px",
                }}
              />

              {snapshotUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={snapshotUrl}
                  alt={`${channelName} preview`}
                  className="block h-auto w-full"
                  draggable={false}
                />
              ) : (
                <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 text-slate-500">
                  {loadingShot ? (
                    <>
                      <Loader2 className="h-8 w-8 animate-spin text-sky-400" />
                      <p className="text-sm">
                        {youtube
                          ? "Resolving YouTube frame… (10–25s)"
                          : "Capturing RTSP frame…"}
                      </p>
                    </>
                  ) : (
                    <>
                      <Crosshair className="h-8 w-8 opacity-50" />
                      <p className="max-w-xs text-center text-sm">
                        {shotError ||
                          "No preview yet — refresh to grab a live frame"}
                      </p>
                    </>
                  )}
                </div>
              )}

              {/* Region overlays — same box as the image */}
              {snapshotUrl &&
                regionKeys.map((key) => {
                const def = regions[key];
                const m = regionMeta[key as keyof typeof regionMeta];
                if (!def || !m) return null;
                const [x1, y1, x2, y2] = def.region;
                const isActive = active === key;
                return (
                  <div
                    key={key}
                    role="button"
                    tabIndex={0}
                    onPointerDown={(e) => startMove(key, e)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") setActive(key);
                    }}
                    className={cn(
                      "absolute z-[2] cursor-move border-2 transition-[box-shadow,opacity]",
                      m.fill,
                      isActive
                        ? cn("z-[3] shadow-[0_0_0_1px_rgba(255,255,255,0.35)]", m.ring, "ring-2")
                        : "opacity-80 hover:opacity-100"
                    )}
                    style={{
                      left: `${x1 * 100}%`,
                      top: `${y1 * 100}%`,
                      width: `${(x2 - x1) * 100}%`,
                      height: `${(y2 - y1) * 100}%`,
                      borderColor: m.color,
                    }}
                  >
                    <div
                      className="pointer-events-none absolute -top-6 start-0 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#0b1220] shadow"
                      style={{ backgroundColor: m.color }}
                    >
                      {m.label}
                    </div>

                    {isActive &&
                      ["nw", "ne", "sw", "se", "n", "s", "e", "w"].map((h) => {
                        const pos: Record<string, string> = {
                          nw: "left-0 top-0 -translate-x-1/2 -translate-y-1/2 cursor-nwse-resize",
                          ne: "right-0 top-0 translate-x-1/2 -translate-y-1/2 cursor-nesw-resize",
                          sw: "left-0 bottom-0 -translate-x-1/2 translate-y-1/2 cursor-nesw-resize",
                          se: "right-0 bottom-0 translate-x-1/2 translate-y-1/2 cursor-nwse-resize",
                          n: "left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 cursor-ns-resize",
                          s: "left-1/2 bottom-0 -translate-x-1/2 translate-y-1/2 cursor-ns-resize",
                          e: "right-0 top-1/2 translate-x-1/2 -translate-y-1/2 cursor-ew-resize",
                          w: "left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize",
                        };
                        return (
                          <button
                            key={h}
                            type="button"
                            aria-label={`Resize ${m.label} ${h}`}
                            className={cn(
                              "absolute z-[4] h-3 w-3 rounded-sm border border-white bg-white shadow",
                              pos[h]
                            )}
                            onPointerDown={(e) => startResize(key, h, e)}
                          />
                        );
                      })}
                  </div>
                );
              })}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
              <span>
                {snapshotMeta
                  ? `${snapshotMeta.w}×${snapshotMeta.h} · source: ${snapshotMeta.source}`
                  : "Waiting for frame"}
              </span>
              {shotError && (
                <span className="text-amber-300/90">{shotError}</span>
              )}
            </div>
          </div>

          {/* Side panel */}
          <aside className="flex flex-col gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Regions
            </p>
            {regionKeys.map((key) => {
              const m = regionMeta[key as keyof typeof regionMeta];
              if (!m) return null;
              const selected = active === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActive(key)}
                  className={cn(
                    "rounded-xl border px-3 py-2.5 text-start transition",
                    selected
                      ? "border-white/25 bg-white/10"
                      : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: m.color }}
                    />
                    <span className="text-sm font-semibold text-white">
                      {m.label}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400">{m.hint}</p>
                </button>
              );
            })}

            {activeDef && meta && (
              <div className="mt-1 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {meta.label} · fractions
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {(["x1", "y1", "x2", "y2"] as const).map((label, idx) => (
                    <label key={label} className="space-y-1">
                      <span className="text-[10px] uppercase text-slate-500">
                        {label}
                      </span>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        max={1}
                        value={activeDef.region[idx]}
                        onChange={(e) => setCoord(idx, e.target.value)}
                        className="h-9 border-white/10 bg-[#0b1220] font-mono text-xs text-slate-100"
                      />
                    </label>
                  ))}
                </div>
                <p className="mt-2 font-mono text-[10px] text-slate-500">
                  conf ≥ {activeDef.min_confidence} · {activeDef.priority}
                </p>
              </div>
            )}
          </aside>
        </div>

        {status && (
          <p className="relative px-6 pb-2 text-xs text-sky-200/90">{status}</p>
        )}

        <DialogFooter className="relative m-0 border-t border-white/10 bg-black/20 px-6 py-4">
          <Button
            type="button"
            variant="outline"
            className="border-white/15 bg-transparent text-slate-200 hover:bg-white/10"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="bg-sky-500 text-slate-950 hover:bg-sky-400"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save regions
          </Button>
        </DialogFooter>
      </div>
    </Dialog>
  );
}

export { DEFAULT_REGIONS, DEFAULT_RTSP_REGIONS, DEFAULT_YOUTUBE_REGIONS, ensureRegionMap };
