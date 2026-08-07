"use client";

import { useState } from "react";
import { Plus, Radio, Trash2, Video } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface RtspChannel {
  name: string;
  rtsp_url: string;
  enabled: boolean;
  priority: string;
}

export interface NewRtspChannelInput {
  name: string;
  rtsp_url: string;
  priority: string;
  enabled: boolean;
}

interface RtspChannelsCardProps {
  defaultUrl: string;
  channels: Record<string, RtspChannel>;
  channelEnabled: Record<string, boolean>;
  onToggle: (id: string, enabled: boolean) => void;
  onAdd?: (channel: NewRtspChannelInput) => Promise<boolean | void>;
  onDelete?: (id: string) => Promise<void>;
  busy?: boolean;
  statusMessage?: string | null;
}

const priorityVariant = (p: string) =>
  p === "high" ? "high" : p === "medium" ? "medium" : "low";

export function RtspChannelsCard({
  defaultUrl,
  channels,
  channelEnabled,
  onToggle,
  onAdd,
  onDelete,
  busy = false,
  statusMessage,
}: RtspChannelsCardProps) {
  const entries = Object.entries(channels);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [rtspUrl, setRtspUrl] = useState(defaultUrl || "");
  const [priority, setPriority] = useState("medium");

  const resetForm = () => {
    setName("");
    setRtspUrl(defaultUrl || "");
    setPriority("medium");
    setShowForm(false);
  };

  const handleAdd = async () => {
    if (!onAdd || busy) return;
    const trimmedName = name.trim();
    const trimmedUrl = rtspUrl.trim();
    if (!trimmedName || !trimmedUrl) return;
    const ok = await onAdd({
      name: trimmedName,
      rtsp_url: trimmedUrl,
      priority,
      enabled: true,
    });
    if (ok !== false) resetForm();
  };

  return (
    <SectionCard
      title="RTSP Channels"
      icon={<Radio className="h-5 w-5 text-primary" />}
      accent="primary"
      contentClassName="font-sans"
    >
      <div dir="ltr" className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            Stored in the database. Enabled channels start automatically with the
            app.
          </p>
          {onAdd && (
            <Button
              type="button"
              size="sm"
              variant={showForm ? "secondary" : "default"}
              onClick={() => setShowForm((v) => !v)}
              disabled={busy}
            >
              <Plus className="h-4 w-4" />
              {showForm ? "Cancel" : "Add channel"}
            </Button>
          )}
        </div>

        {showForm && onAdd && (
          <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-600" htmlFor="new-ch-name">
                Display name
              </label>
              <Input
                id="new-ch-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="News Channel 5"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-600" htmlFor="new-ch-url">
                RTSP URL
              </label>
              <Input
                id="new-ch-url"
                value={rtspUrl}
                onChange={(e) => setRtspUrl(e.target.value)}
                placeholder="rtsp://user:pass@ip:554/Streaming/Channels/501"
                className="font-mono text-xs"
                disabled={busy}
              />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[140px] flex-1 space-y-1.5">
                <label className="text-xs font-medium text-slate-600" htmlFor="new-ch-priority">
                  Priority
                </label>
                <select
                  id="new-ch-priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  disabled={busy}
                  className="flex h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <Button
                type="button"
                onClick={handleAdd}
                disabled={busy || !name.trim() || !rtspUrl.trim()}
              >
                <Plus className="h-4 w-4" />
                Save channel
              </Button>
            </div>
          </div>
        )}

        {statusMessage && (
          <p className="text-xs text-slate-600">{statusMessage}</p>
        )}

        <div className="scroll-panel max-h-[360px] space-y-3 pe-1">
          {entries.length === 0 && (
            <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
              No RTSP channels yet. Add one to start monitoring.
            </p>
          )}
          {entries.map(([id, ch], index) => {
            const enabled = channelEnabled[id] ?? ch.enabled;
            return (
              <article
                key={id}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-slate-300"
              >
                <div className="flex items-start gap-4">
                  <div
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                      enabled ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-400"
                    )}
                  >
                    <Video className="h-5 w-5" />
                  </div>

                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-sm font-semibold text-slate-900">
                        {ch.name}
                      </h4>
                      <Badge
                        variant={priorityVariant(ch.priority)}
                        className="shrink-0 capitalize"
                      >
                        {ch.priority}
                      </Badge>
                      <span
                        className={cn(
                          "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium",
                          enabled
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            enabled ? "bg-emerald-500" : "bg-slate-300"
                          )}
                        />
                        {enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <p className="break-all font-mono text-[11px] leading-relaxed text-slate-500">
                      {ch.rtsp_url}
                    </p>
                  </div>

                  <div className="flex shrink-0 flex-col items-center gap-1.5 border-s border-slate-100 ps-4">
                    <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                      Live
                    </span>
                    <Switch
                      checked={enabled}
                      onCheckedChange={(v) => onToggle(id, v)}
                      aria-label={`Toggle ${ch.name}`}
                      disabled={busy}
                    />
                    <span className="font-mono text-[10px] text-slate-400">
                      CH{index + 1}
                    </span>
                    {onDelete && (
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="mt-1 h-8 w-8 text-slate-400 hover:text-rose"
                        onClick={() => onDelete(id)}
                        disabled={busy}
                        aria-label={`Delete ${ch.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </SectionCard>
  );
}
