import type {
  Alert,
  AppConfig,
  AudioTranscription,
  MonitorStatusResponse,
  StatisticsResponse,
  TextExtraction,
} from "@/lib/types";
import { siteConfig } from "@/config/site";

/**
 * In the browser we use same-origin `/api/*` (proxied by Next.js → Flask).
 * Avoids CORS when the UI is on localhost:3000 and API on 127.0.0.1:5000.
 */
function getApiBase(): string {
  if (typeof window !== "undefined") {
    const explicit = process.env.NEXT_PUBLIC_API_URL?.trim();
    if (explicit) return explicit.replace(/\/$/, "");
    return "";
  }
  return (
    process.env.INTERNAL_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://127.0.0.1:5000"
  ).replace(/\/$/, "");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch (err) {
    const hint =
      base === ""
        ? " Is the Flask backend running? Start: python main.py --mode web"
        : ` Cannot reach ${base}. Check NEXT_PUBLIC_API_URL and that Flask is on port 5000.`;
    throw new Error(
      `Network error${hint} (${err instanceof Error ? err.message : "Failed to fetch"})`
    );
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (data as { error?: string }).error;
    if (res.status === 404) {
      throw new Error(
        msg ?? `HTTP 404 — endpoint not found. Restart Flask: python main.py --mode web`
      );
    }
    throw new Error(msg ?? `HTTP ${res.status}`);
  }
  return data as T;
}

export const api = {
  getStatistics: () => request<StatisticsResponse>("/api/statistics"),

  getMonitorStatus: () =>
    request<MonitorStatusResponse>("/api/monitor/status"),

  getConfig: () => request<AppConfig>("/api/config"),

  getRecentExtractions: (limit = siteConfig.pagination.dashboardExtractions) =>
    request<{ extractions: TextExtraction[]; count: number }>(
      `/api/recent-extractions?limit=${limit}`
    ),

  getRecentTranscriptions: (
    limit = siteConfig.pagination.dashboardTranscriptions
  ) =>
    request<{ transcriptions: AudioTranscription[]; count: number }>(
      `/api/recent-transcriptions?limit=${limit}`
    ),

  getAlerts: (params?: {
    is_read?: boolean;
    type?: string;
    severity?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.is_read !== undefined)
      q.set("is_read", String(params.is_read));
    if (params?.type) q.set("type", params.type);
    if (params?.severity) q.set("severity", params.severity);
    q.set("limit", String(params?.limit ?? siteConfig.pagination.alertsPage));
    return request<{ alerts: Alert[]; count: number }>(`/api/alerts?${q}`);
  },

  markAlertRead: (uuid: string) =>
    request<{ success: boolean }>(`/api/alerts/${uuid}/mark-read`, {
      method: "POST",
    }),

  searchText: (params: {
    q?: string;
    start_date?: string;
    end_date?: string;
    channel?: string;
    region?: string;
    min_confidence?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.start_date) q.set("start_date", params.start_date);
    if (params.end_date) q.set("end_date", params.end_date);
    if (params.channel) q.set("channel", params.channel);
    if (params.region) q.set("region", params.region);
    if (params.min_confidence != null)
      q.set("min_confidence", String(params.min_confidence));
    q.set(
      "limit",
      String(params.limit ?? siteConfig.pagination.searchResults)
    );
    return request<{ results: TextExtraction[]; count: number; query: string }>(
      `/api/search-text?${q}`
    );
  },

  searchAudio: (params: {
    q?: string;
    start_date?: string;
    end_date?: string;
    channel?: string;
    min_confidence?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.start_date) q.set("start_date", params.start_date);
    if (params.end_date) q.set("end_date", params.end_date);
    if (params.channel) q.set("channel", params.channel);
    if (params.min_confidence != null)
      q.set("min_confidence", String(params.min_confidence));
    q.set(
      "limit",
      String(params.limit ?? siteConfig.pagination.searchResults)
    );
    return request<{
      results: AudioTranscription[];
      count: number;
      query: string;
    }>(`/api/search-audio?${q}`);
  },

  startMonitor: (body?: { rtsp_url?: string; channel_name?: string }) =>
    request<{ success: boolean; message?: string; error?: string }>(
      "/api/monitor/start",
      {
        method: "POST",
        body: JSON.stringify({
          rtsp_url: body?.rtsp_url ?? siteConfig.monitor.defaultRtspUrl,
          channel_name:
            body?.channel_name ?? siteConfig.monitor.defaultChannelName,
        }),
      }
    ),

  stopMonitor: () =>
    request<{ success: boolean; message?: string }>("/api/monitor/stop", {
      method: "POST",
    }),
};
