"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { siteConfig } from "@/config/site";

export function useMonitor() {
  const [running, setRunning] = useState(false);
  const [channelName, setChannelName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await api.getMonitorStatus();
      setRunning(status.running);
      setChannelName(status.channel_name);
      const err =
        status.stream_error ?? status.statistics?.stream_error ?? null;
      const captured = status.statistics?.frames_captured ?? 0;
      setStreamError(captured > 0 ? null : err);
    } catch {
      setRunning(false);
      setChannelName(null);
      setStreamError(null);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, siteConfig.api.realtimePollMs);
    return () => clearInterval(id);
  }, [refreshStatus]);

  const start = useCallback(
    async (rtspUrl?: string, channel?: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.startMonitor({
          rtsp_url: rtspUrl ?? siteConfig.monitor.defaultRtspUrl,
          channel_name: channel ?? siteConfig.monitor.defaultChannelName,
        });
        if (res.success) {
          setRunning(true);
          await refreshStatus();
        } else {
          setError(res.error ?? "Failed to start");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start");
      } finally {
        setLoading(false);
      }
    },
    [refreshStatus]
  );

  const stop = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.stopMonitor();
      if (res.success) {
        setRunning(false);
        setChannelName(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop");
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    running,
    channelName,
    loading,
    error,
    streamError,
    start,
    stop,
    refreshStatus,
  };
}
