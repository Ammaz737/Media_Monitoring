"use client";

import { useState } from "react";
import { Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { AlertViewModal } from "@/components/alerts/alert-view-modal";
import type { Alert, AudioTranscription, TextExtraction } from "@/lib/types";
import {
  cn,
  formatTimestamp,
  hasArabicScript,
  parseKeywords,
  screenshotUrl,
  transcriptionAudioUrl,
} from "@/lib/utils";

function ViewFullButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border-0 bg-transparent px-2 py-1 text-[0.8rem] font-medium text-[#1E40AF] transition-colors hover:bg-[#EFF6FF]"
    >
      <Eye className="h-3.5 w-3.5" />
      View Full
    </button>
  );
}

function ConfidenceRow({
  pct,
  forceGreen,
}: {
  pct: number;
  forceGreen?: boolean;
}) {
  const fill = forceGreen
    ? "bg-[#059669]"
    : pct >= 85
      ? "bg-[#059669]"
      : pct >= 70
        ? "bg-[#D97706]"
        : "bg-[#E11D48]";
  return (
    <div className="mt-4 space-y-1.5" dir="ltr">
      <div className="flex items-center justify-between text-[0.78rem] text-slate-500">
        <span>Confidence</span>
        <span className="font-semibold text-slate-700">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-[5px] overflow-hidden rounded-full bg-[#F1F5F9]">
        <div
          className={cn("h-full rounded-full transition-all duration-300", fill)}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

function ModalUrduBlock({ text }: { text: string }) {
  return (
    <p
      className="font-urdu rounded-xl bg-[#F8FAFC] p-4 text-[1.2rem] leading-[2.2] text-[#0F172A]"
      dir="rtl"
    >
      {text}
    </p>
  );
}

function ActivityCardShell({
  borderColor,
  className,
  foldWarm,
  children,
  onView,
}: {
  borderColor: string;
  className?: string;
  foldWarm?: boolean;
  children: React.ReactNode;
  onView: () => void;
}) {
  return (
    <article
      className={cn(
        "group relative flex h-full min-h-[240px] flex-col rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_2px_8px_rgba(0,0,0,0.04)] transition-all duration-200",
        "border-s-[4px] hover:-translate-y-[3px] hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)]",
        borderColor,
        foldWarm && "sticky-note-fold sticky-note-fold--warm",
        className
      )}
    >
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      <div className="mt-auto flex justify-end pt-3">
        <ViewFullButton onClick={onView} />
      </div>
    </article>
  );
}

function regionMeta(regionName: string) {
  const key = regionName.toLowerCase();
  if (key.includes("headline"))
    return { border: "border-s-[#D97706]", pill: "bg-[#FEF3C7] text-[#92400E]" };
  if (key.includes("side"))
    return { border: "border-s-[#7C3AED]", pill: "bg-[#F5F3FF] text-[#6D28D9]" };
  return { border: "border-s-[#2563EB]", pill: "bg-[#EFF6FF] text-[#1D4ED8]" };
}

function AlertKeywordMini({ kw }: { kw: string }) {
  const urdu = hasArabicScript(kw);
  return (
    <span
      dir={urdu ? "rtl" : "ltr"}
      className={cn(
        "inline-flex h-[22px] items-center rounded-[6px] border px-2 text-[0.72rem] font-semibold leading-none",
        urdu
          ? "keyword-tag-urdu border-[#C7D2FE] bg-[#EEF2FF] text-[#3730A3]"
          : "border-[#BBF7D0] bg-[#F0FDF4] text-[#166534]"
      )}
    >
      {kw}
    </span>
  );
}

export function ExtractionStickyCard({ item }: { item: TextExtraction }) {
  const [open, setOpen] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const confidencePct = item.confidence * 100;
  const meta = regionMeta(item.region_name);
  const shotUrl = screenshotUrl(item.screenshot_path);

  return (
    <>
      <ActivityCardShell borderColor={meta.border} onView={() => setOpen(true)}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-[0.75rem] font-bold capitalize",
                meta.pill
              )}
            >
              {item.region_name}
            </span>
            {(item.ocr_engine || "utrnet").toLowerCase() === "ollama" ? (
              <span className="rounded-full bg-[#7C3AED] px-2.5 py-0.5 text-[0.7rem] font-bold text-white">
                Ollama
              </span>
            ) : (
              <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-0.5 text-[0.7rem] font-medium text-slate-600">
                UTRNet
              </span>
            )}
          </div>
          <span className="shrink-0 text-[0.72rem] text-slate-400" dir="ltr">
            {formatTimestamp(item.timestamp)}
          </span>
        </div>
        <p
          className="font-urdu mt-4 min-h-[80px] flex-1 text-[1.05rem] font-medium leading-[2] text-[#1E293B] line-clamp-4"
          dir="rtl"
        >
          {item.extracted_text}
        </p>
        <ConfidenceRow pct={confidencePct} />
        <span className="mt-3 inline-flex w-fit rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-[0.72rem] font-medium text-slate-600">
          {item.channel_name}
        </span>
      </ActivityCardShell>

      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (next) setImgFailed(false);
        }}
      >
        <div className="pe-8">
          <p className="mb-2 text-sm text-slate-500" dir="ltr">
            {formatTimestamp(item.timestamp)} · {item.channel_name} ·{" "}
            <span className="capitalize">{item.region_name}</span>
            {" · "}
            {(item.ocr_engine || "utrnet").toLowerCase() === "ollama"
              ? "Ollama"
              : "UTRNet"}
          </p>
          {shotUrl && !imgFailed ? (
            <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-[#0F172A]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={shotUrl}
                alt={`OCR crop — ${item.region_name}`}
                className="max-h-[280px] w-full object-contain"
                onError={() => setImgFailed(true)}
              />
            </div>
          ) : (
            <p
              className="mb-4 rounded-xl border border-dashed border-slate-200 bg-[#F8FAFC] px-3 py-6 text-center text-sm text-slate-400"
              dir="ltr"
            >
              No screenshot available for this extraction
            </p>
          )}
          <ModalUrduBlock text={item.extracted_text} />
          <div className="mt-4" dir="ltr">
            <Progress value={confidencePct} barClassName="bg-[#059669]" />
            <p className="mt-1.5 text-right text-xs text-slate-500">
              Confidence {confidencePct.toFixed(1)}%
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}

export function TranscriptionStickyCard({ item }: { item: AudioTranscription }) {
  const [open, setOpen] = useState(false);
  const confidencePct = item.confidence * 100;
  const audioUrl = transcriptionAudioUrl(item.audio_path);

  return (
    <>
      <ActivityCardShell
        borderColor="border-s-[#059669]"
        onView={() => setOpen(true)}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-[#D1FAE5] px-2.5 py-0.5 text-[0.75rem] font-bold text-[#065F46]">
              Audio
            </span>
            <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 text-[0.72rem] text-slate-500">
              {item.duration.toFixed(1)}s
            </span>
          </div>
          <span className="shrink-0 text-[0.72rem] text-slate-400" dir="ltr">
            {formatTimestamp(item.timestamp)}
          </span>
        </div>
        <p
          className="font-urdu mt-4 min-h-[80px] flex-1 text-[1rem] font-medium leading-[2] text-[#1E293B] line-clamp-4"
          dir="rtl"
        >
          {item.transcribed_text}
        </p>
        <ConfidenceRow pct={confidencePct} forceGreen />
        <span className="mt-3 inline-flex w-fit rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-[0.72rem] font-medium text-slate-600">
          {item.channel_name}
        </span>
      </ActivityCardShell>

      <Dialog open={open} onOpenChange={setOpen}>
        <div className="pe-8">
          <p className="mb-2 text-sm text-slate-500" dir="ltr">
            {item.duration.toFixed(1)}s · {item.channel_name}
          </p>
          {audioUrl ? (
            <div className="mb-4 overflow-hidden rounded-xl border border-slate-200 bg-[#F8FAFC] p-3">
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <audio
                controls
                preload="metadata"
                src={audioUrl}
                className="h-10 w-full"
              />
            </div>
          ) : (
            <p
              className="mb-4 rounded-xl border border-dashed border-slate-200 bg-[#F8FAFC] px-3 py-4 text-center text-sm text-slate-400"
              dir="ltr"
            >
              No audio clip saved for this transcription
            </p>
          )}
          <ModalUrduBlock text={item.transcribed_text} />
          <Progress value={confidencePct} barClassName="mt-4 bg-[#059669]" />
        </div>
        <DialogFooter>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}

export function AlertStickyCard({
  item,
  onMarkRead,
}: {
  item: Alert;
  onMarkRead?: (uuid: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const keywords = parseKeywords(item.matched_keywords);

  return (
    <>
      <ActivityCardShell
        borderColor="border-s-[#D97706]"
        className="bg-[#FFFBEB] border-[#FDE68A]"
        foldWarm
        onView={() => setOpen(true)}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="rounded-full bg-[#FEF3C7] px-2.5 py-0.5 text-[0.75rem] font-bold text-[#92400E]">
            Alert
          </span>
          <span className="shrink-0 text-[0.72rem] text-slate-400" dir="ltr">
            {formatTimestamp(item.timestamp)}
          </span>
        </div>
        <p
          className="font-urdu mt-4 min-h-[72px] flex-1 text-end text-[1.05rem] font-medium leading-[2] text-[#1E293B] line-clamp-4"
          dir="rtl"
        >
          {item.alert_text}
        </p>
        {keywords.length > 0 && (
          <div className="mt-3 flex flex-wrap justify-end gap-1.5">
            {keywords.slice(0, 4).map((kw) => (
              <AlertKeywordMini key={kw} kw={kw} />
            ))}
          </div>
        )}
      </ActivityCardShell>

      <AlertViewModal
        item={item}
        open={open}
        onOpenChange={setOpen}
        onMarkRead={onMarkRead}
      />
    </>
  );
}
