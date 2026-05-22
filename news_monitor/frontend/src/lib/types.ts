export interface TextExtraction {
  uuid: string;
  timestamp: string;
  region_name: string;
  extracted_text: string;
  confidence: number;
  priority: string;
  channel_name: string;
  region_coords?: string;
  frame_hash?: string;
  screenshot_path?: string;
}

export interface AudioTranscription {
  uuid: string;
  timestamp: string;
  transcribed_text: string;
  confidence: number;
  duration: number;
  channel_name: string;
  language?: string;
  audio_path?: string;
}

export interface Alert {
  uuid: string;
  timestamp: string;
  alert_type: string;
  content_type: string;
  content_id: string;
  matched_keywords: string | string[];
  alert_text: string;
  severity: "high" | "medium" | "low" | string;
  is_read: boolean;
}

export interface DatabaseStats {
  period: { start: string; end: string };
  totals: {
    text_extractions: number;
    audio_transcriptions: number;
    alerts: number;
    unread_alerts: number;
  };
  period_totals?: {
    text_extractions: number;
    audio_transcriptions: number;
    alerts: number;
  };
  recent_activity: {
    text_extractions_24h: number;
    audio_transcriptions_24h: number;
  };
  chart_series?: { time: string; extractions: number; transcriptions: number }[];
}

export interface MonitorStats {
  runtime_seconds?: number;
  frames_per_second?: number;
  extractions_per_minute?: number;
  queue_sizes?: { frames?: number; audio?: number };
  is_running?: boolean;
  channel_name?: string;
  text_extractions?: number;
  audio_transcriptions?: number;
  alerts_triggered?: number;
  source_url?: string;
  stream_error?: string | null;
  frames_processed?: number;
  frames_captured?: number;
}

export interface StatisticsResponse {
  database: DatabaseStats;
  monitor: MonitorStats;
  timestamp: string;
}

export interface MonitorStatusResponse {
  running: boolean;
  channel_name: string | null;
  source_url?: string;
  stream_error?: string | null;
  statistics: MonitorStats;
}

export interface AppConfig {
  rtsp_url: string;
  rtsp_channels: Record<
    string,
    { name: string; rtsp_url: string; enabled: boolean; priority: string }
  >;
  text_regions: Record<
    string,
    { name: string; region: number[]; priority: string; min_confidence: number }
  >;
  processing: Record<string, number | boolean>;
  speech: Record<string, unknown>;
  utrnet: Record<string, unknown>;
  alerts: {
    enabled: boolean;
    keywords: string[];
    notification_methods: string[];
  };
  web: { max_search_results: number; results_per_page: number };
}

export interface RealtimeUpdate {
  timestamp: string;
  recent_extractions?: TextExtraction[];
  recent_transcriptions?: AudioTranscription[];
  recent_alerts?: Alert[];
  statistics?: MonitorStats;
}
