/**
 * Global application settings — single source of truth for UI & API defaults.
 */
export const siteConfig = {
  name: "News Monitor",
  nameUrdu: "نیوز مانیٹر",
  description: "TVeyes-like Urdu news monitoring dashboard",
  direction: "rtl" as const,
  locale: "ur-PK",

  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "",
    socketUrl:
      process.env.NEXT_PUBLIC_SOCKET_URL ?? "http://localhost:5000",
    refreshIntervalMs: 30_000,
    realtimePollMs: 5_000,
    chartMaxPoints: 20,
  },

  monitor: {
    defaultRtspUrl:
      "rtsp://admin:gcs12345@192.168.2.145:554/Streaming/Channels/101",
    defaultChannelName: "news_channel",
  },

  pagination: {
    dashboardExtractions: 10,
    dashboardTranscriptions: 10,
    dashboardAlerts: 5,
    searchResults: 50,
    alertsPage: 100,
  },

  nav: [
    { href: "/", label: "Dashboard", labelUrdu: "ڈیش بورڈ" },
    { href: "/search", label: "Search", labelUrdu: "تلاش" },
    { href: "/alerts", label: "Alerts", labelUrdu: "الرٹس" },
    { href: "/settings", label: "Settings", labelUrdu: "ترتیبات" },
  ],

  theme: {
    page: "#F8FAFC",
    card: "#FFFFFF",
    primary: "#1E40AF",
    success: "#059669",
    warning: "#D97706",
    rose: "#E11D48",
    border: "#E2E8F0",
    text: "#111827",
    muted: "#64748B",
  },
} as const;

export type SiteConfig = typeof siteConfig;
