import type {
  Alert,
  AppConfig,
  AudioTranscription,
  AuthUser,
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

/** Direct Flask origin — used for long-running / streaming requests (avoid Next proxy timeout). */
export function getFlaskDirectBase(): string {
  const explicit =
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.INTERNAL_API_URL?.trim() ||
    process.env.FLASK_API_URL?.trim();
  if (explicit) return explicit.replace(/\/$/, "");
  return "http://127.0.0.1:5000";
}

export const TOKEN_KEY = "nm_token";

export function getAuthToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** NVR playback RTSP → browser MP4 stream URL (video + audio). */
export function getTrackStreamUrl(params: {
  channel_id: string;
  start: string;
  duration: number;
}): string {
  const q = new URLSearchParams({
    channel_id: params.channel_id,
    start: params.start,
    duration: String(params.duration),
  });
  const token = getAuthToken();
  if (token) q.set("token", token);
  return `${getFlaskDirectBase()}/api/tracks/stream?${q}`;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  opts?: { baseUrl?: string }
): Promise<T> {
  const base = opts?.baseUrl ?? getApiBase();
  const url = `${base}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
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
    if (
      res.status === 401 &&
      typeof window !== "undefined" &&
      !path.startsWith("/api/auth/login")
    ) {
      setAuthToken(null);
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    const msg = (data as { error?: string; hint?: string }).error;
    const extra = (data as { hint?: string }).hint;
    if (res.status === 404) {
      throw new Error(
        msg ?? `HTTP 404 — endpoint not found. Restart Flask: python main.py --mode web`
      );
    }
    const detail = msg
      ? extra
        ? `${msg} ${extra}`
        : msg
      : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<{ user: AuthUser }>("/api/auth/me"),

  logout: () =>
    request<{ success: boolean }>("/api/auth/logout", { method: "POST" }),

  listUsers: () => request<{ users: AuthUser[] }>("/api/users"),

  createUser: (body: { username: string; password: string; role: string }) =>
    request<{ user: AuthUser }>("/api/users", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateUser: (
    id: number,
    body: { password?: string; role?: string; is_active?: boolean }
  ) =>
    request<{ user: AuthUser }>(`/api/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  deleteUser: (id: number) =>
    request<{ success: boolean }>(`/api/users/${id}`, { method: "DELETE" }),

  getStatistics: () => request<StatisticsResponse>("/api/statistics"),

  getMonitorStatus: () =>
    request<MonitorStatusResponse>("/api/monitor/status"),

  getConfig: () => request<AppConfig>("/api/config"),

  updateKeywords: (body: {
    action?: "add" | "remove" | "set";
    keyword?: string;
    keywords?: string[];
  }) =>
    request<{
      success: boolean;
      keywords: string[];
      alerts_created?: number;
      error?: string;
    }>("/api/config/keywords", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getSearchFacets: () =>
    request<{ channels: string[]; regions: string[] }>("/api/search-facets"),

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
    return request<{
      alerts: Alert[];
      count: number;
      totals?: { total: number; unread: number; read: number };
    }>(`/api/alerts?${q}`);
  },

  markAlertRead: (uuid: string) =>
    request<{ success: boolean }>(`/api/alerts/${uuid}/mark-read`, {
      method: "POST",
    }),

  markAllAlertsRead: () =>
    request<{ success: boolean; updated?: number }>(
      "/api/alerts/mark-all-read",
      { method: "POST" }
    ),

  searchText: (params: {
    q?: string;
    start_date?: string;
    end_date?: string;
    channel?: string;
    region?: string;
    fuzzy_threshold?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.start_date) q.set("start_date", params.start_date);
    if (params.end_date) q.set("end_date", params.end_date);
    if (params.channel) q.set("channel", params.channel);
    if (params.region) q.set("region", params.region);
    if (params.fuzzy_threshold != null)
      q.set("fuzzy_threshold", String(params.fuzzy_threshold));
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
    fuzzy_threshold?: number;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.q) q.set("q", params.q);
    if (params.start_date) q.set("start_date", params.start_date);
    if (params.end_date) q.set("end_date", params.end_date);
    if (params.channel) q.set("channel", params.channel);
    if (params.fuzzy_threshold != null)
      q.set("fuzzy_threshold", String(params.fuzzy_threshold));
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

  startMonitor: (body?: {
    rtsp_url?: string;
    channel_name?: string;
    multi_channel?: boolean;
    enabled_channels?: Record<string, boolean>;
  }) =>
    request<{
      success: boolean;
      message?: string;
      error?: string;
      multi_channel?: boolean;
      channels?: string[];
    }>("/api/monitor/start", {
      method: "POST",
      body: JSON.stringify({
        multi_channel: body?.multi_channel ?? true,
        rtsp_url: body?.rtsp_url ?? siteConfig.monitor.defaultRtspUrl,
        channel_name:
          body?.channel_name ?? siteConfig.monitor.defaultChannelName,
        ...(body?.enabled_channels
          ? { enabled_channels: body.enabled_channels }
          : {}),
      }),
    }),

  updateChannel: (channelId: string, enabled: boolean) =>
    request<{
      success: boolean;
      channel_id: string;
      enabled: boolean;
      channels?: AppConfig["rtsp_channels"];
      error?: string;
    }>(`/api/config/channels/${channelId}`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  updateChannelUrl: (channelId: string, rtsp_url: string) =>
    request<{
      success: boolean;
      channel_id: string;
      channel: AppConfig["rtsp_channels"][string];
      channels: AppConfig["rtsp_channels"];
      error?: string;
    }>(`/api/config/channels/${encodeURIComponent(channelId)}`, {
      method: "POST",
      body: JSON.stringify({ rtsp_url }),
    }),

  updateChannelRegions: (
    channelId: string,
    text_regions: AppConfig["rtsp_channels"][string]["text_regions"] | null
  ) =>
    request<{
      success: boolean;
      channel_id: string;
      channel: AppConfig["rtsp_channels"][string];
      channels: AppConfig["rtsp_channels"];
      error?: string;
    }>(`/api/config/channels/${channelId}`, {
      method: "POST",
      body: JSON.stringify({ text_regions }),
    }),

  getChannelSnapshot: async (channelId: string) => {
    // Hit Flask directly — YouTube resolve + ffmpeg can exceed Next rewrite defaults
    const base = getFlaskDirectBase();
    const url = `${base}/api/config/channels/${encodeURIComponent(channelId)}/snapshot`;
    let res: Response;
    try {
      res = await fetch(url, {
        cache: "no-store",
        headers: authHeaders(),
      });
    } catch (err) {
      throw new Error(
        `Network error loading snapshot (${err instanceof Error ? err.message : "Failed to fetch"})`
      );
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(
        (data as { error?: string }).error ?? `HTTP ${res.status}`
      );
    }
    const blob = await res.blob();
    return {
      url: URL.createObjectURL(blob),
      width: Number(res.headers.get("X-Frame-Width") || 0),
      height: Number(res.headers.get("X-Frame-Height") || 0),
      source: res.headers.get("X-Snapshot-Source") || "unknown",
    };
  },

  createChannel: (body: {
    name: string;
    rtsp_url: string;
    priority?: string;
    enabled?: boolean;
    channel_id?: string;
  }) =>
    request<{
      success: boolean;
      channel_id: string;
      channel: AppConfig["rtsp_channels"][string];
      channels: AppConfig["rtsp_channels"];
      error?: string;
    }>("/api/config/channels", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  deleteChannel: (channelId: string) =>
    request<{
      success: boolean;
      channel_id: string;
      deleted?: boolean;
      channels: AppConfig["rtsp_channels"];
      error?: string;
    }>(`/api/config/channels/${channelId}`, {
      method: "DELETE",
    }),

  stopMonitor: () =>
    request<{ success: boolean; message?: string }>("/api/monitor/stop", {
      method: "POST",
    }),

  extractTrackClip: async (body: {
    channel_id: string;
    start: string;
    duration: number;
  }) => {
    // Bypass Next.js rewrite — 30s+ NVR pulls hit the default ~30s proxy timeout (HTTP 500).
    const res = await request<{
      success: boolean;
      clip_id: string;
      url: string;
      channel_id: string;
      channel_name: string;
      start: string;
      end: string;
      duration: number;
      error?: string;
      hint?: string;
    }>(
      "/api/tracks/clip",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
      { baseUrl: getFlaskDirectBase() }
    );
    // Serve the wav via same-origin rewrite (fast GET); keep relative path for <audio>.
    return res;
  },
};
