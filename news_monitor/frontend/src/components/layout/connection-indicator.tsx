"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ConnectionIndicatorProps {
  connected: boolean | null;
}

export function ConnectionIndicator({ connected }: ConnectionIndicatorProps) {
  if (connected === null) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3.5 py-1.5 text-xs font-medium text-slate-500">
        <Loader2 className="h-3 w-3 animate-spin" />
        اتصال...
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-150",
        connected
          ? "border border-emerald-200/80 bg-[#F0FDF4] text-green-700"
          : "border border-[#E2E8F0] bg-[#F8FAFC] text-slate-500"
      )}
    >
      <span className="relative flex h-2 w-2">
        {connected && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            connected ? "bg-emerald-500" : "bg-slate-400"
          )}
        />
      </span>
      {connected ? "متصل" : "غیر فعال"}
    </span>
  );
}
