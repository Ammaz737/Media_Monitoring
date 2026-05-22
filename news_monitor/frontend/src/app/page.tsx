"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { StatsGrid } from "@/components/dashboard/stats-grid";
import { ActivityTabs } from "@/components/dashboard/activity-tabs";
import {
  ActivityChart,
  type ChartPoint,
} from "@/components/dashboard/activity-chart";
import { SystemStatus } from "@/components/dashboard/system-status";
import { api } from "@/lib/api";
import { subscribeRealtime } from "@/lib/socket";
import { siteConfig } from "@/config/site";
import { useMonitor } from "@/hooks/use-monitor";
import type {
  Alert,
  AudioTranscription,
  DatabaseStats,
  MonitorStats,
  RealtimeUpdate,
  TextExtraction,
} from "@/lib/types";

export default function DashboardPage() {
  const monitor = useMonitor();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [dbStats, setDbStats] = useState<DatabaseStats | undefined>();
  const [monStats, setMonStats] = useState<MonitorStats | undefined>();
  const [extractions, setExtractions] = useState<TextExtraction[]>([]);
  const [transcriptions, setTranscriptions] = useState<AudioTranscription[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [configStreamUrl, setConfigStreamUrl] = useState<string>(
    siteConfig.monitor.defaultRtspUrl
  );

  const applyUpdate = useCallback((data: {
    statistics?: { database?: DatabaseStats; monitor?: MonitorStats };
    recent_extractions?: TextExtraction[];
    recent_transcriptions?: AudioTranscription[];
    recent_alerts?: Alert[];
  }) => {
    if (data.statistics?.database) setDbStats(data.statistics.database);
    if (data.statistics?.monitor) setMonStats(data.statistics.monitor);

    if (data.recent_extractions) setExtractions(data.recent_extractions);
    if (data.recent_transcriptions)
      setTranscriptions(data.recent_transcriptions);
    if (data.recent_alerts) setAlerts(data.recent_alerts);

    const pushChartPoint = (
      extractionsVal: number,
      transcriptionsVal: number
    ) => {
      const now = new Date().toLocaleTimeString();
      setChartData((prev) => {
        const next = [
          ...prev,
          { time: now, extractions: extractionsVal, transcriptions: transcriptionsVal },
        ];
        return next.slice(-siteConfig.api.chartMaxPoints);
      });
    };

    if (data.statistics?.database?.chart_series?.length) {
      setChartData(data.statistics.database.chart_series);
    } else if (data.statistics?.database?.recent_activity) {
      const ra = data.statistics.database.recent_activity;
      pushChartPoint(
        ra.text_extractions_24h ?? 0,
        ra.audio_transcriptions_24h ?? 0
      );
    }
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [stats, ext, tr, al, status] = await Promise.all([
        api.getStatistics(),
        api.getRecentExtractions(),
        api.getRecentTranscriptions(),
        api.getAlerts({
          is_read: false,
          limit: siteConfig.pagination.dashboardAlerts,
        }),
        api.getMonitorStatus(),
      ]);
      applyUpdate({
        statistics: {
          database: stats.database,
          monitor: {
            ...stats.monitor,
            ...status.statistics,
            is_running: status.running,
            frames_captured: status.statistics?.frames_captured,
            frames_processed: status.statistics?.frames_processed,
            stream_error: status.stream_error ?? status.statistics?.stream_error,
          },
        },
        recent_extractions: ext.extractions,
        recent_transcriptions: tr.transcriptions,
        recent_alerts: al.alerts,
      });
      if (stats.monitor?.is_running !== undefined) {
        /* useMonitor polls separately */
      }
    } finally {
      setLoading(false);
    }
  }, [applyUpdate]);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, siteConfig.api.refreshIntervalMs);
    return () => clearInterval(interval);
  }, [loadAll]);

  useEffect(() => {
    api
      .getConfig()
      .then((c) => {
        if (c.rtsp_url) setConfigStreamUrl(c.rtsp_url);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const unsub = subscribeRealtime(
      (data: RealtimeUpdate) => {
        applyUpdate({
          statistics: data.statistics
            ? { monitor: data.statistics }
            : undefined,
          recent_extractions: data.recent_extractions,
          recent_transcriptions: data.recent_transcriptions,
          recent_alerts: data.recent_alerts,
        });
        if (data.statistics?.is_running !== undefined) {
          monitor.refreshStatus();
        }
      },
      () => setConnected(true),
      () => setConnected(false)
    );
    return unsub;
  }, [applyUpdate, monitor]);

  const handleMarkRead = async (uuid: string) => {
    await api.markAlertRead(uuid);
    await loadAll();
  };

  const handleStartMonitor = async (url: string, channel: string) => {
    await monitor.start(url, channel);
    await loadAll();
  };

  return (
    <AppShell monitorRunning={monitor.running} connected={connected}>
      <StatsGrid database={dbStats} monitor={monStats} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <ActivityChart data={chartData} />
        </div>
        <div className="lg:col-span-4">
          <SystemStatus
            monitor={monStats}
            running={monitor.running}
            loading={monitor.loading}
            error={monitor.error}
            streamError={monitor.streamError ?? monStats?.stream_error}
            queueSize={
              (monStats?.queue_sizes?.frames ?? 0) +
              (monStats?.queue_sizes?.audio ?? 0)
            }
            framesProcessed={monStats?.frames_processed ?? 0}
            framesCaptured={monStats?.frames_captured ?? 0}
            defaultStreamUrl={configStreamUrl}
            onStart={handleStartMonitor}
            onStop={() => monitor.stop()}
          />
        </div>
      </div>

      <ActivityTabs
        extractions={extractions}
        transcriptions={transcriptions}
        alerts={alerts}
        loading={loading}
        onMarkAlertRead={handleMarkRead}
      />
    </AppShell>
  );
}
