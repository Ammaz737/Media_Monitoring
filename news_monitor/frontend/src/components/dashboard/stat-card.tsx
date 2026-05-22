"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/use-count-up";

interface StatCardProps {
  title: string;
  icon: LucideIcon;
  numericValue: number;
  decimals?: number;
  label: string;
  badge?: { text: string; variant: "amber" | "blue" | "teal" | "gray" };
  iconBg: string;
  iconColor: string;
  staggerIndex?: number;
}

const badgeStyles = {
  amber:
    "bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]",
  blue: "bg-[#EFF6FF] text-[#1E40AF] border border-[#BFDBFE]",
  teal: "bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0]",
  gray: "bg-[#F1F5F9] text-[#64748B] border border-[#E2E8F0] font-mono",
};

export function StatCard({
  title,
  icon: Icon,
  numericValue,
  decimals = 0,
  label,
  badge,
  iconBg,
  iconColor,
  staggerIndex = 0,
}: StatCardProps) {
  const display = useCountUp(numericValue, 1200, decimals);

  return (
    <article
      className="dashboard-stagger-in group relative overflow-hidden rounded-[20px] border border-[#F1F5F9] bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)] transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-[0_4px_12px_rgba(0,0,0,0.08),0_12px_32px_rgba(0,0,0,0.1)]"
      style={{ animationDelay: `${staggerIndex * 50}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className={cn(
            "flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-[14px]",
            iconBg
          )}
        >
          <Icon className={cn("h-6 w-6", iconColor)} strokeWidth={2} />
        </div>
        <span className="pt-1 text-[0.8rem] font-medium uppercase tracking-[0.06em] text-slate-400">
          {title}
        </span>
      </div>

      <p className="mt-5 text-[2.8rem] font-extrabold leading-none tracking-tight text-[#0F172A]">
        {display}
      </p>
      <p className="mt-2 text-[0.82rem] text-slate-500">{label}</p>

      {badge && (
        <div className="relative z-10 mt-4">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.75rem] font-semibold",
              badgeStyles[badge.variant]
            )}
          >
            {badge.variant === "amber" && (
              <span className="h-1.5 w-1.5 rounded-full bg-[#D97706]" />
            )}
            {badge.text}
          </span>
        </div>
      )}

      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[rgba(248,250,252,0.8)] to-transparent"
        aria-hidden
      />
    </article>
  );
}
