import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { TextExtraction } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";
import {
  getRegionBadgeVariant,
  getRegionBorderClass,
} from "@/lib/region-styles";
import { cn } from "@/lib/utils";

export function ExtractionItem({ item }: { item: TextExtraction }) {
  const confidencePct = item.confidence * 100;

  return (
    <div
      className={cn(
        "mb-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-150",
        "border-s-4",
        getRegionBorderClass(item.region_name)
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <Badge variant={getRegionBadgeVariant(item.region_name)}>
          {item.region_name}
        </Badge>
        <span className="shrink-0 text-xs text-slate-400" dir="ltr">
          {formatTimestamp(item.timestamp)}
        </span>
      </div>
      <p className="urdu-text line-clamp-3 text-slate-900">{item.extracted_text}</p>
      <div className="mt-3 space-y-2" dir="ltr">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Confidence</span>
          <span className="font-medium text-slate-700">
            {confidencePct.toFixed(1)}%
          </span>
        </div>
        <Progress value={confidencePct} />
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span>Priority: {item.priority}</span>
          <Badge variant="channel" className="text-[10px]">
            {item.channel_name}
          </Badge>
        </div>
      </div>
    </div>
  );
}
