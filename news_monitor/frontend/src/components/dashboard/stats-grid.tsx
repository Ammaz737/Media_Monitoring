"use client";

import { FileText, Mic, Bell, Zap } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import type { DatabaseStats, MonitorStats } from "@/lib/types";

interface StatsGridProps {
  database?: DatabaseStats;
  monitor?: MonitorStats;
}

export function StatsGrid({ database, monitor }: StatsGridProps) {
  const db = database?.totals;
  const recent = database?.recent_activity;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        staggerIndex={0}
        title="Performance"
        icon={Zap}
        numericValue={monitor?.extractions_per_minute ?? 0}
        decimals={1}
        label="Extractions/min"
        badge={{
          text: `${(monitor?.frames_per_second ?? 0).toFixed(1)} FPS`,
          variant: "gray",
        }}
        iconBg="bg-[#EFF6FF]"
        iconColor="text-[#2563EB]"
      />
      <StatCard
        staggerIndex={1}
        title="Alerts"
        icon={Bell}
        numericValue={db?.alerts ?? 0}
        label="Total alerts"
        badge={{
          text: `${db?.unread_alerts ?? 0} unread`,
          variant: "amber",
        }}
        iconBg="bg-[#FEF3C7]"
        iconColor="text-[#D97706]"
      />
      <StatCard
        staggerIndex={2}
        title="Audio Transcriptions"
        icon={Mic}
        numericValue={db?.audio_transcriptions ?? 0}
        label="Total transcriptions"
        badge={{
          text: `${recent?.audio_transcriptions_24h ?? 0} in last 24h`,
          variant: "blue",
        }}
        iconBg="bg-[#F5F3FF]"
        iconColor="text-[#7C3AED]"
      />
      <StatCard
        staggerIndex={3}
        title="Text Extractions"
        icon={FileText}
        numericValue={db?.text_extractions ?? 0}
        label="Total extractions"
        badge={{
          text: `${recent?.text_extractions_24h ?? 0} in last 24h`,
          variant: "teal",
        }}
        iconBg="bg-[#F0FDF4]"
        iconColor="text-[#059669]"
      />
    </div>
  );
}
