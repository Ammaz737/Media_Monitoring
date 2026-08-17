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
import { UsersCard } from "@/components/settings/users-card";
import { useAuth } from "@/components/auth/auth-provider";

export function SettingsPanel() {
  const { can } = useAuth();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [channelEnabled, setChannelEnabled] = useState<Record<string, boolean>>(
    {}
  );
  const [usingFallback, setUsingFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keywordBusy, setKeywordBusy] = useState(false);
  const [keywordStatus, setKeywordStatus] = useState<string | null>(null);
  const [channelBusy, setChannelBusy] = useState(false);
  const [channelStatus, setChannelStatus] = useState<string | null>(null);

  const applyChannels = (channels: AppConfig["rtsp_channels"]) => {
    setConfig((prev) => (prev ? { ...prev, rtsp_channels: channels } : prev));
    const enabled: Record<string, boolean> = {};
    Object.entries(channels).forEach(([id, ch]) => {
      enabled[id] = ch.enabled;
    });
    setChannelEnabled(enabled);
  };

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

  const addKeyword = async () => {
    const kw = newKeyword.trim();
    if (!kw || keywords.includes(kw) || keywordBusy) return;
    if (usingFallback) {
      setKeywords([...keywords, kw]);
      setNewKeyword("");
      setKeywordStatus("Saved locally only — start Flask to persist");
      return;
    }
    setKeywordBusy(true);
    setKeywordStatus(null);
    try {
      const res = await api.updateKeywords({ action: "add", keyword: kw });
      setKeywords(res.keywords);
      setNewKeyword("");
      const created = res.alerts_created ?? 0;
      setKeywordStatus(
        created > 0
          ? `Saved. Matched ${created} recent extraction(s) → Alerts`
          : "Keyword saved"
      );
    } catch (e) {
      setKeywordStatus(e instanceof Error ? e.message : "Failed to save keyword");
    } finally {
      setKeywordBusy(false);
    }
  };

  const removeKeyword = async (kw: string) => {
    if (keywordBusy) return;
    if (usingFallback) {
      setKeywords(keywords.filter((k) => k !== kw));
      return;
    }
    setKeywordBusy(true);
    setKeywordStatus(null);
    try {
      const res = await api.updateKeywords({ action: "remove", keyword: kw });
      setKeywords(res.keywords);
      setKeywordStatus("Keyword removed");
    } catch (e) {
      setKeywordStatus(
        e instanceof Error ? e.message : "Failed to remove keyword"
      );
    } finally {
      setKeywordBusy(false);
    }
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
          busy={channelBusy}
          statusMessage={channelStatus}
          onChannelsUpdated={(channels) => {
            applyChannels(channels);
            setChannelStatus("OCR regions saved");
          }}
          onToggle={async (id, enabled) => {
            setChannelEnabled((prev) => ({ ...prev, [id]: enabled }));
            if (usingFallback) return;
            try {
              const res = await api.updateChannel(id, enabled);
              if (res.channels) applyChannels(res.channels);
            } catch (e) {
              setChannelEnabled((prev) => ({ ...prev, [id]: !enabled }));
              setChannelStatus(
                e instanceof Error ? e.message : "Failed to update channel"
              );
            }
          }}
          onAdd={
            usingFallback
              ? undefined
              : async (channel) => {
                  setChannelBusy(true);
                  setChannelStatus(null);
                  try {
                    const res = await api.createChannel(channel);
                    applyChannels(res.channels);
                    setChannelStatus(`Added ${res.channel.name}`);
                    return true;
                  } catch (e) {
                    setChannelStatus(
                      e instanceof Error ? e.message : "Failed to add channel"
                    );
                    return false;
                  } finally {
                    setChannelBusy(false);
                  }
                }
          }
          onDelete={
            usingFallback
              ? undefined
              : async (id) => {
                  setChannelBusy(true);
                  setChannelStatus(null);
                  try {
                    const res = await api.deleteChannel(id);
                    applyChannels(res.channels);
                    setChannelStatus("Channel removed");
                  } catch (e) {
                    setChannelStatus(
                      e instanceof Error
                        ? e.message
                        : "Failed to delete channel"
                    );
                  } finally {
                    setChannelBusy(false);
                  }
                }
          }
          onUpdateUrl={
            usingFallback
              ? undefined
              : async (id, rtspUrl) => {
                  setChannelBusy(true);
                  setChannelStatus(null);
                  try {
                    const res = await api.updateChannelUrl(id, rtspUrl);
                    applyChannels(res.channels);
                    setChannelStatus(`Updated URL for ${res.channel.name}`);
                    return true;
                  } catch (e) {
                    setChannelStatus(
                      e instanceof Error ? e.message : "Failed to update URL"
                    );
                    return false;
                  } finally {
                    setChannelBusy(false);
                  }
                }
          }
        />

        <AlertKeywordsCard
          keywords={keywords}
          newKeyword={newKeyword}
          onNewKeywordChange={setNewKeyword}
          onAddKeyword={addKeyword}
          onRemoveKeyword={removeKeyword}
          notificationMethods={config.alerts.notification_methods}
          busy={keywordBusy}
          statusMessage={keywordStatus}
        />
      </div>
      {can("users") && <UsersCard />}
    </div>
  );
}
