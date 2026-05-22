"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";

export interface ChartPoint {
  time: string;
  extractions: number;
  transcriptions: number;
}

interface ActivityChartProps {
  data: ChartPoint[];
}

type ChartFocus = "all" | "text" | "audio";

function PulseDot(props: {
  cx?: number;
  cy?: number;
  index?: number;
  dataLength: number;
  color: string;
}) {
  const { cx, cy, index, dataLength, color } = props;
  if (cx == null || cy == null || index !== dataLength - 1) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill={color} opacity={0.2} className="chart-pulse-ring" />
      <circle cx={cx} cy={cy} r={5} fill={color} stroke="#fff" strokeWidth={2} />
    </g>
  );
}

export function ActivityChart({ data }: ActivityChartProps) {
  const [focus, setFocus] = useState<ChartFocus>("all");
  const chartData = data.length
    ? data
    : [{ time: "—", extractions: 0, transcriptions: 0 }];

  const showText = focus === "all" || focus === "text";
  const showAudio = focus === "all" || focus === "audio";

  const pills = useMemo(
    () => [
      { id: "text" as const, label: "Text", href: "/?tab=extractions" },
      { id: "audio" as const, label: "Audio", href: "/?tab=transcriptions" },
    ],
    []
  );

  return (
    <div
      className="dashboard-stagger-in flex h-full flex-col rounded-[20px] border border-[#F1F5F9] bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)]"
      style={{ animationDelay: "150ms" }}
    >
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-bold text-slate-900">Activity Chart</h3>
        <div className="flex flex-wrap justify-end gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
            <span className="h-2 w-2 rounded-full bg-[#2563EB]" />
            Text Extractions
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
            <span className="h-2 w-2 rounded-full bg-[#7C3AED]" />
            Audio Transcriptions
          </span>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="flex rounded-full bg-[#F1F5F9] p-1">
            <button
              type="button"
              onClick={() => setFocus("all")}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-all",
                focus === "all"
                  ? "bg-[#1E40AF] text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              )}
            >
              All
            </button>
            {pills.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setFocus(p.id)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-all",
                  focus === p.id
                    ? "bg-[#1E40AF] text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
      </div>

      <div className="h-[280px] min-h-[200px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%" minHeight={200}>
          <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="fillExtractions" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#2563EB" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="fillTranscriptions" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#F1F5F9" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 11, fill: "#CBD5E1" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 12,
                border: "1px solid #E2E8F0",
                boxShadow: "0 8px 24px rgba(0,0,0,0.1)",
                background: "#fff",
                fontSize: 12,
              }}
            />
            {showText && (
              <Area
                type="monotone"
                dataKey="extractions"
                name="Text Extractions"
                stroke="#2563EB"
                strokeWidth={3}
                fill="url(#fillExtractions)"
                isAnimationActive
                animationDuration={1200}
                animationEasing="ease-out"
                dot={(props) => (
                  <PulseDot
                    {...props}
                    dataLength={chartData.length}
                    color="#2563EB"
                  />
                )}
                activeDot={{ r: 6 }}
              />
            )}
            {showAudio && (
              <Area
                type="monotone"
                dataKey="transcriptions"
                name="Audio Transcriptions"
                stroke="#7C3AED"
                strokeWidth={3}
                fill="url(#fillTranscriptions)"
                isAnimationActive
                animationDuration={1200}
                animationEasing="ease-out"
                dot={(props) => (
                  <PulseDot
                    {...props}
                    dataLength={chartData.length}
                    color="#7C3AED"
                  />
                )}
                activeDot={{ r: 6 }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <Link
          href="/?tab=extractions"
          className="text-xs font-medium text-[#1E40AF] hover:underline"
        >
          View extractions →
        </Link>
        <Link
          href="/?tab=transcriptions"
          className="text-xs font-medium text-[#7C3AED] hover:underline"
        >
          View audio →
        </Link>
      </div>
    </div>
  );
}
