import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { AudioTranscription } from "@/lib/types";
import { formatTimestamp, transcriptionAudioUrl } from "@/lib/utils";

export function TranscriptionItem({ item }: { item: AudioTranscription }) {
  const confidencePct = item.confidence * 100;
  const audioUrl = transcriptionAudioUrl(item.audio_path);

  return (
    <div className="mb-3 rounded-xl border border-slate-200 border-s-4 border-s-success bg-white p-4 shadow-sm transition-all duration-150">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant="success">Audio</Badge>
          <Badge variant="channel">{item.duration.toFixed(1)}s</Badge>
        </div>
        <span className="shrink-0 text-xs text-slate-400" dir="ltr">
          {formatTimestamp(item.timestamp)}
        </span>
      </div>
      {audioUrl && (
        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-2">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls preload="metadata" src={audioUrl} className="h-9 w-full" />
        </div>
      )}
      <p className="urdu-text line-clamp-3 text-slate-900">{item.transcribed_text}</p>
      <div className="mt-3 space-y-2" dir="ltr">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Confidence</span>
          <span className="font-medium">{confidencePct.toFixed(1)}%</span>
        </div>
        <Progress value={confidencePct} barClassName="bg-success" />
        <Badge variant="channel" className="text-[10px]">
          {item.channel_name}
        </Badge>
      </div>
    </div>
  );
}
