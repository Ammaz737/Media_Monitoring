"use client";

import type { ReactNode } from "react";
import {
  AlertTriangle,
  Bell,
  Check,
  Clock,
  Copy,
  FileText,
  Mic,
  Shield,
} from "lucide-react";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Alert } from "@/lib/types";
import { cn, formatTimestamp, hasArabicScript, parseKeywords } from "@/lib/utils";

function severityConfidence(severity: string): number {
  const s = severity?.toLowerCase();
  if (s === "high") return 92;
  if (s === "low") return 55;
  return 72;
}

function severityStyles(severity: string) {
  const s = severity?.toLowerCase() ?? "medium";
  if (s === "high") {
    return {
      badge: "bg-[#FEE2E2] text-[#991B1B] ring-[#FECACA]",
      bar: "bg-[#DC2626]",
      icon: "bg-[#FEE2E2] text-[#DC2626]",
      accent: "border-s-[#DC2626]",
    };
  }
  if (s === "low") {
    return {
      badge: "bg-[#DCFCE7] text-[#166534] ring-[#BBF7D0]",
      bar: "bg-[#059669]",
      icon: "bg-[#DCFCE7] text-[#059669]",
      accent: "border-s-[#059669]",
    };
  }
  return {
    badge: "bg-[#FEF3C7] text-[#92400E] ring-[#FDE68A]",
    bar: "bg-[#D97706]",
    icon: "bg-[#FEF3C7] text-[#D97706]",
    accent: "border-s-[#D97706]",
  };
}

function MetaTile({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#E2E8F0] bg-white px-3 py-2">
      <div className="mb-0.5 flex items-center gap-1 text-[0.65rem] font-semibold uppercase tracking-wider text-[#64748B]">
        {icon}
        {label}
      </div>
      <p className="text-[0.85rem] font-bold capitalize text-[#0F172A]">{value}</p>
    </div>
  );
}

interface AlertViewModalProps {
  item: Alert | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onMarkRead?: (uuid: string) => void;
}

export function AlertViewModal({
  item,
  open,
  onOpenChange,
  onMarkRead,
}: AlertViewModalProps) {
  if (!item) return null;

  const keywords = parseKeywords(item.matched_keywords);
  const isUnread = !item.is_read;
  const confidence = severityConfidence(item.severity);
  const styles = severityStyles(item.severity);
  const isAudio =
    item.content_type?.toLowerCase().includes("audio") ||
    item.content_type?.toLowerCase().includes("transcription");
  const urdu = hasArabicScript(item.alert_text);

  const copyId = () => {
    void navigator.clipboard?.writeText(item.uuid);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      className="max-w-[560px] p-0"
    >
      <div className="overflow-hidden rounded-2xl">
        {/* Header — compact */}
        <div className="border-b border-[#E2E8F0] bg-gradient-to-r from-[#FFFBEB] via-white to-[#EFF6FF] px-5 pb-3.5 pt-4 pe-12">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                styles.icon
              )}
            >
              <Bell className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <h2 className="text-base font-bold text-[#0F172A]">Alert details</h2>
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-[0.65rem] font-bold capitalize ring-1 ring-inset",
                    styles.badge
                  )}
                >
                  {item.severity || "medium"}
                </span>
                {isUnread ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#1E40AF] px-1.5 py-0.5 text-[0.62rem] font-bold uppercase text-white">
                    <span className="h-1 w-1 animate-pulse rounded-full bg-white" />
                    Unread
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-[#F1F5F9] px-1.5 py-0.5 text-[0.62rem] font-semibold text-[#64748B]">
                    <Check className="h-2.5 w-2.5" />
                    Read
                  </span>
                )}
              </div>
              <p
                className="flex items-center gap-1 text-[0.78rem] text-[#64748B]"
                dir="ltr"
              >
                <Clock className="h-3 w-3 shrink-0" />
                {formatTimestamp(item.timestamp)}
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-3.5 px-5 py-4">
          {keywords.length > 0 && (
            <section>
              <p className="mb-1.5 text-[0.65rem] font-semibold uppercase tracking-wider text-[#64748B]">
                Matched keywords
              </p>
              <div className="flex flex-wrap gap-1.5">
                {keywords.map((kw) => {
                  const kwUrdu = hasArabicScript(kw);
                  return (
                    <span
                      key={kw}
                      dir={kwUrdu ? "rtl" : "ltr"}
                      className={cn(
                        "inline-flex min-h-[28px] items-center rounded-md px-2.5 py-1 text-[0.78rem] font-semibold",
                        kwUrdu
                          ? "keyword-tag-urdu border border-[#C7D2FE] bg-[#EEF2FF] text-[#3730A3]"
                          : "border border-[#BBF7D0] bg-[#F0FDF4] font-sans text-[#166534]"
                      )}
                    >
                      {kw}
                    </span>
                  );
                })}
              </div>
            </section>
          )}

          <section>
            <p className="mb-1.5 text-[0.65rem] font-semibold uppercase tracking-wider text-[#64748B]">
              Alert message
            </p>
            <div
              className={cn(
                "rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3",
                "border-s-[3px]",
                styles.accent
              )}
              dir={urdu ? "rtl" : "ltr"}
            >
              <p
                className={cn(
                  "whitespace-pre-wrap break-words text-[#0F172A]",
                  urdu
                    ? "font-urdu text-[1.15rem] font-medium leading-[2.15]"
                    : "font-sans text-[0.95rem] leading-relaxed"
                )}
              >
                {item.alert_text}
              </p>
            </div>
          </section>

          <div className="grid grid-cols-3 gap-2" dir="ltr">
            <MetaTile
              label="Severity"
              value={item.severity || "medium"}
              icon={<AlertTriangle className="h-3 w-3" />}
            />
            <MetaTile
              label="Content"
              value={isAudio ? "Audio" : "Text"}
              icon={
                isAudio ? (
                  <Mic className="h-3 w-3" />
                ) : (
                  <FileText className="h-3 w-3" />
                )
              }
            />
            <MetaTile
              label="Type"
              value={item.alert_type?.replace(/_/g, " ") || "keyword"}
              icon={<Shield className="h-3 w-3" />}
            />
          </div>

          <div
            className="flex items-center gap-4 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2.5"
            dir="ltr"
          >
            <div className="min-w-0 flex-1">
              <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-[#64748B]">
                Match strength
              </p>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#E2E8F0]">
                <div
                  className={cn("h-full rounded-full transition-all", styles.bar)}
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>
            <p className="shrink-0 text-2xl font-bold tabular-nums text-[#1E40AF]">
              {confidence.toFixed(0)}%
            </p>
          </div>

          <button
            type="button"
            onClick={copyId}
            className="group flex w-full items-center gap-2 rounded-md border border-dashed border-[#E2E8F0] px-2.5 py-1.5 text-start hover:bg-[#F8FAFC]"
            dir="ltr"
            title={item.uuid}
          >
            <Copy className="h-3 w-3 shrink-0 text-[#94A3B8]" />
            <span className="min-w-0 flex-1 truncate font-mono text-[0.62rem] text-[#94A3B8]">
              {item.uuid}
            </span>
          </button>
        </div>
      </div>

      <DialogFooter className="mt-0 border-t border-[#E2E8F0] bg-[#F8FAFC] px-5 py-3 sm:justify-between">
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          {onMarkRead && isUnread && (
            <Button
              size="sm"
              className="gap-1.5 rounded-lg bg-[#1E40AF] hover:bg-[#1E3A8A]"
              onClick={() => {
                onMarkRead(item.uuid);
                onOpenChange(false);
              }}
            >
              <Check className="h-3.5 w-3.5" />
              Mark as Read
            </Button>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          className="rounded-lg"
          onClick={() => onOpenChange(false)}
        >
          Close
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
