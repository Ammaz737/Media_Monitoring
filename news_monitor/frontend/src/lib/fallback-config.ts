import { siteConfig } from "@/config/site";
import type { AppConfig } from "@/lib/types";

/** Used when Flask has not been restarted and /api/config is missing (404). */
export function getFallbackAppConfig(): AppConfig {
  return {
    rtsp_url: siteConfig.monitor.defaultRtspUrl,
    rtsp_channels: {
      channel_1: {
        name: "News Channel 1",
        rtsp_url: siteConfig.monitor.defaultRtspUrl,
        enabled: true,
        priority: "high",
      },
      channel_2: {
        name: "News Channel 2",
        rtsp_url:
          "rtsp://admin:Admin123.@192.168.2.144:554/Streaming/Channels/401",
        enabled: true,
        priority: "medium",
      },
    },
    text_regions: {
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
    },
    processing: {
      frame_interval: 2.0,
      batch_size: 4,
      max_queue_size: 100,
    },
    speech: {
      enabled: true,
      model: "openai/whisper-small",
      chunk_duration: 30,
    },
    utrnet: {
      FeatureExtraction: "HRNet",
      SequenceModeling: "DBiLSTM",
      Prediction: "CTC",
    },
    alerts: {
      enabled: true,
      keywords: ["breaking", "urgent", "عاجل", "خبر", "اہم"],
      notification_methods: ["web", "email", "webhook"],
    },
    web: {
      max_search_results: 1000,
      results_per_page: 50,
    },
  };
}
