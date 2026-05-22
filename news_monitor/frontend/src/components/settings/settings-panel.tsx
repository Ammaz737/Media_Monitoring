"use client";

import { useEffect, useState } from "react";
import { Layers, Settings2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { getFallbackAppConfig } from "@/lib/fallback-config";
import type { AppConfig } from "@/lib/types";
import { SectionCard } from "@/components/ui/section-card";
import { AlertKeywordsCard } from "@/components/settings/alert-keywords-card";
import { RtspChannelsCard } from "@/components/settings/rtsp-channels-card";
import { Badge } from "@/components/ui/badge";
import { siteConfig } from "@/config/site";

export function SettingsPanel() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [channelEnabled, setChannelEnabled] = useState<Record<string, boolean>>(
    {}
  );
  const [usingFallback, setUsingFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getConfig()
      .then((data) => {
        setConfig(data);
        setKeywords([...data.alerts.keywords]);
        const enabled: Record<string, boolean> = {};
        Object.entries(data.rtsp_channels).forEach(([id, ch]) => {
          enabled[id] = ch.enabled;
        });
        setChannelEnabled(enabled);
        setUsingFallback(false);
        setError(null);
      })
      .catch((e) => {
        const message = e instanceof Error ? e.message : "Failed to load";
        if (message.includes("404")) {
          const fb = getFallbackAppConfig();
          setConfig(fb);
          setKeywords([...fb.alerts.keywords]);
          const enabled: Record<string, boolean> = {};
          Object.entries(fb.rtsp_channels).forEach(([id, ch]) => {
            enabled[id] = ch.enabled;
          });
          setChannelEnabled(enabled);
          setUsingFallback(true);
        } else {
          setError(message);
        }
      });
  }, []);

  const addKeyword = () => {
    const kw = newKeyword.trim();
    if (kw && !keywords.includes(kw)) {
      setKeywords([...keywords, kw]);
      setNewKeyword("");
    }
  };

  const removeKeyword = (kw: string) => {
    setKeywords(keywords.filter((k) => k !== kw));
  };

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center text-rose">
        {error}
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-4 font-sans" dir="ltr">
      {usingFallback && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Showing cached settings — restart Flask for live config:{" "}
          <code className="rounded bg-white/80 px-1 text-xs">
            python main.py --mode web
          </code>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <RtspChannelsCard
          defaultUrl={config.rtsp_url}
          channels={config.rtsp_channels}
          channelEnabled={channelEnabled}
          onToggle={(id, enabled) =>
            setChannelEnabled((prev) => ({ ...prev, [id]: enabled }))
          }
        />

        <AlertKeywordsCard
          keywords={keywords}
          newKeyword={newKeyword}
          onNewKeywordChange={setNewKeyword}
          onAddKeyword={addKeyword}
          onRemoveKeyword={removeKeyword}
          notificationMethods={config.alerts.notification_methods}
        />

        <SectionCard
          title="Text Regions"
          icon={<Layers className="h-5 w-5 text-primary" />}
          accent="purple"
        >
          <div className="space-y-3">
            {Object.entries(config.text_regions).map(([key, r]) => (
              <div
                key={key}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <strong className="text-sm font-semibold text-slate-900">
                      {r.name}
                    </strong>
                    <p className="mt-1 font-sans text-xs text-slate-500">
                      Key: <span className="font-mono">{key}</span> · Min
                      confidence: {r.min_confidence}
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className="shrink-0 font-mono text-[10px] font-normal"
                  >
                    [{r.region.join(", ")}]
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Processing & Web"
          icon={<Settings2 className="h-5 w-5 text-primary" />}
          accent="teal"
        >
          <dl className="divide-y divide-slate-100">
            {[
              ["Frame interval", `${config.processing.frame_interval}s`],
              ["Batch size", String(config.processing.batch_size)],
              ["Max queue", String(config.processing.max_queue_size)],
              ["Speech model", String(config.speech.model)],
              ["Results per page", String(config.web.results_per_page)],
              ["Max search results", String(config.web.max_search_results)],
              [
                "Frontend API",
                siteConfig.api.baseUrl || "(proxied /api)",
              ],
            ].map(([label, value]) => (
              <div
                key={label}
                className="flex items-center justify-between gap-6 py-3 first:pt-0"
              >
                <dt className="shrink-0 text-sm font-medium text-slate-600">
                  {label}
                </dt>
                <dd className="text-end font-mono text-sm text-slate-800">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </SectionCard>
      </div>
    </div>
  );
}
