"use client";

import { Radio, Video } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

interface Channel {
  name: string;
  rtsp_url: string;
  enabled: boolean;
  priority: string;
}

interface RtspChannelsCardProps {
  defaultUrl: string;
  channels: Record<string, Channel>;
  channelEnabled: Record<string, boolean>;
  onToggle: (id: string, enabled: boolean) => void;
}

const priorityVariant = (p: string) =>
  p === "high" ? "high" : p === "medium" ? "medium" : "low";

export function RtspChannelsCard({
  defaultUrl,
  channels,
  channelEnabled,
  onToggle,
}: RtspChannelsCardProps) {
  const entries = Object.entries(channels);

  return (
    <SectionCard
      title="RTSP Channels"
      icon={<Radio className="h-5 w-5 text-primary" />}
      accent="primary"
      contentClassName="font-sans"
    >
      <div dir="ltr" className="space-y-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2.5">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Default stream
          </p>
          <p className="break-all font-mono text-[11px] leading-relaxed text-slate-600">
            {defaultUrl}
          </p>
        </div>

        <div className="space-y-3">
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
                    />
                    <span className="font-mono text-[10px] text-slate-400">
                      CH{index + 1}
                    </span>
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
