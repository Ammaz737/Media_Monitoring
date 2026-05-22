"use client";

import { useState } from "react";
import { Check, Clock, Eye, Newspaper } from "lucide-react";
import type { Alert } from "@/lib/types";
import {
  cn,
  formatTimestamp,
  hasArabicScript,
  parseKeywords,
} from "@/lib/utils";
import { AlertViewModal } from "@/components/alerts/alert-view-modal";

interface AlertCardProps {
  item: Alert;
  onMarkRead?: (uuid: string) => void;
}

const MAX_KEYWORDS = 4;

function MatchKeywordPill({
  keyword,
  isPrimary = false,
}: {
  keyword: string;
  isPrimary?: boolean;
}) {
  const urdu = hasArabicScript(keyword);
  return (
    <span
      dir={urdu ? "rtl" : "ltr"}
      className={cn(
        "inline-flex h-[26px] max-h-[26px] shrink-0 items-center justify-center rounded-[6px] border px-2.5 font-semibold leading-none",
        isPrimary &&
          "border-[#FDE68A] bg-[#FEF3C7] text-[0.78rem] text-[#92400E]",
        !isPrimary &&
          urdu &&
          "keyword-tag-urdu border-[#C7D2FE] bg-[#EEF2FF] text-[0.82rem] text-[#3730A3]",
        !isPrimary &&
          !urdu &&
          "border-[#BBF7D0] bg-[#F0FDF4] font-sans text-[0.78rem] text-[#166534]"
      )}
    >
      {keyword}
    </span>
  );
}

function MoreKeywordsPill({ count }: { count: number }) {
  return (
    <span className="inline-flex h-[26px] items-center justify-center rounded-[6px] border border-[#E2E8F0] bg-[#F1F5F9] px-2.5 text-[0.78rem] font-semibold leading-none text-[#64748B]">
      +{count}
    </span>
  );
}

function PriorityBadge({ severity }: { severity: string }) {
  const s = severity?.toLowerCase() ?? "medium";
  const isHigh = s === "high";
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-[0.7rem] font-bold capitalize",
        isHigh
          ? "bg-[#FEE2E2] text-[#991B1B]"
          : "bg-[#FEF3C7] text-[#92400E]"
      )}
    >
      {severity || "medium"}
    </span>
  );
}

function TypeBadge({ contentType }: { contentType: string }) {
  const t = contentType?.toLowerCase() ?? "";
  const isAudio = t.includes("audio") || t.includes("transcription");
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[0.7rem] font-semibold text-[#1D4ED8]">
      <span aria-hidden>{isAudio ? "🎵" : "📄"}</span>
      {isAudio ? "audio" : "text"}
    </span>
  );
}

export function AlertCard({ item, onMarkRead }: AlertCardProps) {
  const [viewOpen, setViewOpen] = useState(false);
  const keywords = parseKeywords(item.matched_keywords);
  const isUnread = !item.is_read;
  const displayKeywords =
    keywords.length > 0 ? keywords : [item.alert_type || "alert"];
  const visibleKw = displayKeywords.slice(0, MAX_KEYWORDS);
  const extraKw = displayKeywords.length - MAX_KEYWORDS;
  const textLong = item.alert_text.length > 120;

  return (
    <>
      <article
        dir="ltr"
        className={cn(
          "group relative rounded-2xl border p-5 shadow-[0_2px_8px_rgba(0,0,0,0.05)] transition-all duration-150 ease-out",
          "hover:-translate-y-[3px] hover:shadow-[0_8px_24px_rgba(0,0,0,0.1)]",
          "border-s-[4px]",
          isUnread
            ? "border border-[#FDE68A] border-s-[#D97706] bg-[#FFFDF0]"
            : "border border-[#E2E8F0] border-s-[#CBD5E1] bg-white"
        )}
      >
        {isUnread && (
          <span className="alert-new-pulse absolute -top-2 end-4 rounded-full bg-[#D97706] px-2 py-0.5 text-[0.65rem] font-extrabold uppercase tracking-wider text-white">
            NEW
          </span>
        )}

        {/* Top row */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#1E40AF] to-[#3B82F6] text-white shadow-md">
              <Newspaper className="h-5 w-5" strokeWidth={2} />
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              <p className="text-[0.72rem] text-slate-400">keyword match</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {visibleKw.map((kw, i) => (
                  <MatchKeywordPill
                    key={kw}
                    keyword={kw}
                    isPrimary={i === 0}
                  />
                ))}
                {extraKw > 0 && <MoreKeywordsPill count={extraKw} />}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-end gap-1">
            {isUnread && (
              <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[0.7rem] font-bold text-[#D97706]">
                NEW
              </span>
            )}
            <PriorityBadge severity={item.severity} />
            <TypeBadge contentType={item.content_type} />
          </div>
        </div>

        {/* Urdu content */}
        <div
          className="mt-4 min-h-[60px] rounded-[10px] bg-white/70 px-4 py-3"
          dir="rtl"
        >
          <p
            className={cn(
              "text-right font-urdu text-[1.15rem] font-medium leading-[2.2] text-[#1E293B] max-md:text-[1rem]",
              textLong && "line-clamp-2",
              !hasArabicScript(item.alert_text) && "font-sans text-left"
            )}
          >
            {item.alert_text}
            {textLong && "…"}
          </p>
        </div>

        {/* Bottom row */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-[0.75rem] text-slate-400">
              <Clock className="h-3.5 w-3.5 shrink-0" />
              {formatTimestamp(item.timestamp)}
            </p>
            <p className="mt-0.5 max-w-[120px] truncate font-mono text-[0.7rem] text-slate-300">
              {item.uuid}
            </p>
          </div>

          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <button
              type="button"
              onClick={() => setViewOpen(true)}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[#BFDBFE] bg-transparent px-3.5 py-1.5 text-[0.8rem] font-medium text-[#1E40AF] transition-colors hover:bg-[#EFF6FF] sm:flex-initial"
            >
              <Eye className="h-4 w-4" />
              View
            </button>
            {isUnread && onMarkRead ? (
              <button
                type="button"
                onClick={() => onMarkRead(item.uuid)}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[#1E40AF] px-3.5 py-1.5 text-[0.8rem] font-medium text-white transition-colors hover:bg-[#1E3A8A] sm:flex-initial"
              >
                <Check className="h-4 w-4" />
                Read
              </button>
            ) : (
              <span className="inline-flex flex-1 items-center justify-center gap-1 text-[0.8rem] text-slate-400 sm:flex-initial">
                <Check className="h-4 w-4 text-emerald-600" />
                Read
              </span>
            )}
          </div>
        </div>
      </article>

      <AlertViewModal
        item={item}
        open={viewOpen}
        onOpenChange={setViewOpen}
        onMarkRead={onMarkRead}
      />
    </>
  );
}
