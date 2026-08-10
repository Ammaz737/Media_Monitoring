"use client";

import { useState } from "react";
import { Eye } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import type { TextExtraction } from "@/lib/types";
import {
  cn,
  formatTimestamp,
  screenshotUrl,
} from "@/lib/utils";
import {
  getRegionBadgeVariant,
  getRegionBorderClass,
} from "@/lib/region-styles";

export function ExtractionItem({ item }: { item: TextExtraction }) {
  const [open, setOpen] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const confidencePct = item.confidence * 100;
  const shotUrl = screenshotUrl(item.screenshot_path);

  return (
    <>
      <div
        className={cn(
          "mb-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-150",
          "border-s-4",
          getRegionBorderClass(item.region_name)
        )}
      >
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant={getRegionBadgeVariant(item.region_name)}>
              {item.region_name}
            </Badge>
            {(item.ocr_engine || "utrnet").toLowerCase() === "ollama" ? (
              <Badge className="bg-[#7C3AED] text-[10px] text-white hover:bg-[#7C3AED]">
                Ollama
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-[10px]">
                UTRNet
              </Badge>
            )}
          </div>
          <span className="shrink-0 text-xs text-slate-400" dir="ltr">
            {formatTimestamp(item.timestamp)}
          </span>
        </div>
        <p className="urdu-text line-clamp-3 py-3 leading-[2.15] text-slate-900">
          {item.extracted_text}
        </p>
        <div className="mt-3 space-y-2" dir="ltr">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Confidence</span>
            <span className="font-medium text-slate-700">
              {confidencePct.toFixed(1)}%
            </span>
          </div>
          <Progress value={confidencePct} />
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <div className="flex flex-wrap items-center gap-2">
              <span>Priority: {item.priority}</span>
              <Badge variant="channel" className="text-[10px]">
                {item.channel_name}
              </Badge>
            </div>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border-0 bg-transparent px-2 py-1 text-[0.8rem] font-medium text-[#1E40AF] transition-colors hover:bg-[#EFF6FF]"
            >
              <Eye className="h-3.5 w-3.5" />
              View
            </button>
          </div>
        </div>
      </div>

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
          <p
            className="urdu-text rounded-xl bg-[#F8FAFC] px-4 py-4 leading-[2.2] text-[#0F172A]"
          >
            {item.extracted_text}
          </p>
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
