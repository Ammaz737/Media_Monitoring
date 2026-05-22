"use client";

import { useEffect, useState } from "react";
import { Monitor, ArrowRight, Square, Link2, Radio } from "lucide-react";
import { formatRuntime } from "@/lib/utils";
import type { MonitorStats } from "@/lib/types";
import { cn } from "@/lib/utils";
import { siteConfig } from "@/config/site";

const STORAGE_URL = "news_monitor_stream_url";
const STORAGE_CHANNEL = "news_monitor_channel_name";

interface SystemStatusProps {
  monitor?: MonitorStats;
  running: boolean;
  loading?: boolean;
  error?: string | null;
  streamError?: string | null;
  queueSize?: number;
  framesProcessed?: number;
  framesCaptured?: number;
  defaultStreamUrl?: string;
  onStart: (rtspUrl: string, channelName: string) => void;
  onStop: () => void;
}

export function SystemStatus({
  monitor,
  running,
  loading,
  error,
  streamError,
  queueSize = 0,
  framesProcessed = 0,
  framesCaptured = 0,
  defaultStreamUrl,
  onStart,
  onStop,
}: SystemStatusProps) {
  const [streamUrl, setStreamUrl] = useState(
    siteConfig.monitor.defaultRtspUrl
  );
  const [channelName, setChannelName] = useState(
    siteConfig.monitor.defaultChannelName
  );

  useEffect(() => {
    const savedUrl = localStorage.getItem(STORAGE_URL);
    const savedChannel = localStorage.getItem(STORAGE_CHANNEL);
    if (savedUrl) setStreamUrl(savedUrl);
    else if (defaultStreamUrl) setStreamUrl(defaultStreamUrl);
    if (savedChannel) setChannelName(savedChannel);
  }, [defaultStreamUrl]);

  const queueTotal =
    queueSize > 0
      ? queueSize
      : (monitor?.queue_sizes?.frames ?? 0) +
        (monitor?.queue_sizes?.audio ?? 0);
  const runtime = formatRuntime(monitor?.runtime_seconds ?? 0);

  const handleStart = () => {
    const url = streamUrl.trim();
    const channel = channelName.trim() || siteConfig.monitor.defaultChannelName;
    if (!url) return;
    localStorage.setItem(STORAGE_URL, url);
    localStorage.setItem(STORAGE_CHANNEL, channel);
    onStart(url, channel);
  };

  return (
    <div
      className="dashboard-stagger-in flex h-full flex-col rounded-[20px] bg-gradient-to-br from-[#0F172A] to-[#1E293B] p-7 text-white shadow-[0_8px_32px_rgba(15,23,42,0.35)]"
      style={{ animationDelay: "200ms" }}
      dir="ltr"
    >
      <div className="mb-4 flex items-center gap-2">
        <Monitor className="h-5 w-5 text-sky-400" />
        <h3 className="text-base font-bold">System Status</h3>
        {running && (
          <span className="ms-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            Live
          </span>
        )}
      </div>

      {/* Stream URL input */}
      <div className="mb-5 space-y-3">
        <div>
          <label
            htmlFor="stream-url"
            className="mb-1.5 flex items-center gap-1.5 text-[0.72rem] font-medium uppercase tracking-wider text-slate-400"
          >
            <Link2 className="h-3.5 w-3.5" />
            Video / RTSP link
          </label>
          <input
            id="stream-url"
            type="url"
            value={streamUrl}
            onChange={(e) => setStreamUrl(e.target.value)}
            disabled={running || loading}
            placeholder="rtsp://user:pass@ip:554/..."
            className="w-full rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2.5 font-mono text-xs text-white placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-60"
          />
          <p className="mt-1.5 text-[0.68rem] leading-relaxed text-slate-500">
            RTSP (rtsp://...) ya YouTube live link. YouTube ke liye Flask par{" "}
            <code className="text-sky-300">pip install yt-dlp</code> chahiye.
          </p>
        </div>
        <div>
          <label
            htmlFor="channel-name"
            className="mb-1.5 flex items-center gap-1.5 text-[0.72rem] font-medium uppercase tracking-wider text-slate-400"
          >
            <Radio className="h-3.5 w-3.5" />
            Channel name
          </label>
          <input
            id="channel-name"
            type="text"
            value={channelName}
            onChange={(e) => setChannelName(e.target.value)}
            disabled={running || loading}
            placeholder="news_channel"
            className="w-full rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 disabled:opacity-60"
          />
        </div>
        {error && (
          <p className="rounded-lg bg-rose-500/15 px-3 py-2 text-xs text-rose-200">
            {error}
          </p>
        )}
        {running && streamError && (
          <p className="rounded-lg bg-sky-500/15 px-3 py-2 text-xs text-sky-100">
            {streamError}
          </p>
        )}
        {running && !streamError && framesCaptured > 0 && (
          <p className="rounded-lg bg-emerald-500/15 px-3 py-2 text-xs text-emerald-200">
            Stream OK — Queue: {queueSize} · Captured: {framesCaptured} · OCR:{" "}
            {framesProcessed}
          </p>
        )}
        {running && !streamError && framesCaptured === 0 && (
          <p className="rounded-lg bg-slate-700/50 px-3 py-2 text-xs text-slate-300">
            Waiting for first frame… YouTube may take 10–20 sec
          </p>
        )}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Runtime
          </p>
          <p className="mt-1 font-mono text-[1.8rem] font-bold leading-none text-[#38BDF8]">
            {runtime}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Queue Size
          </p>
          <p className="mt-1 text-[2rem] font-bold leading-none text-[#34D399]">
            {queueTotal}
          </p>
        </div>
      </div>

      <div className="mt-auto grid gap-3">
        <button
          type="button"
          disabled={running || loading || !streamUrl.trim()}
          onClick={handleStart}
          className={cn(
            "group flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 text-sm font-semibold text-white transition-all duration-200",
            "bg-gradient-to-br from-[#1E40AF] to-[#3B82F6] shadow-[0_4px_15px_rgba(59,130,246,0.4)]",
            "hover:scale-[1.02] hover:shadow-[0_6px_22px_rgba(59,130,246,0.55)]",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
          )}
        >
          Start Monitoring
          <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
        </button>
        <button
          type="button"
          disabled={!running || loading}
          onClick={onStop}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3.5 text-sm font-semibold text-white transition-all duration-200",
            "bg-gradient-to-br from-[#9F1239] to-[#E11D48] shadow-[0_4px_15px_rgba(225,29,72,0.35)]",
            "hover:scale-[1.02] hover:shadow-[0_6px_20px_rgba(225,29,72,0.45)]",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
          )}
        >
          <Square className="h-4 w-4 fill-current" />
          Stop Monitoring
        </button>
      </div>
    </div>
  );
}
