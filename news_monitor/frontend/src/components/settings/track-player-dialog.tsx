"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Video } from "lucide-react";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getTrackStreamUrl } from "@/lib/api";

interface TrackPlayerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channelId: string;
  channelName: string;
}

function defaultLocalDatetime(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function TrackPlayerDialog({
  open,
  onOpenChange,
  channelId,
  channelName,
}: TrackPlayerDialogProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [start, setStart] = useState(defaultLocalDatetime);
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setStreamUrl(null);
      setLoading(false);
      return;
    }
    setStart(defaultLocalDatetime());
    setDuration(30);
    setError(null);
    setStreamUrl(null);
    setLoading(false);
  }, [open, channelId]);

  // Tear down stream when dialog closes so ffmpeg stops
  useEffect(() => {
    if (!open && videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
  }, [open]);

  const canSubmit = useMemo(
    () => Boolean(start) && duration >= 1 && duration <= 300 && !loading,
    [start, duration, loading]
  );

  const handlePlay = () => {
    if (!canSubmit) return;
    setError(null);
    setLoading(true);
    const url = getTrackStreamUrl({
      channel_id: channelId,
      start,
      duration,
    });
    // Bust cache so replay with same params restarts the RTSP pull
    setStreamUrl(`${url}&_=${Date.now()}`);
  };

  const handleClose = () => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
    setStreamUrl(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose} className="max-w-2xl p-6">
      <div className="pe-8" dir="ltr">
        <div className="mb-1 flex items-center gap-2 text-primary">
          <Video className="h-5 w-5" />
          <h3 className="text-lg font-semibold text-slate-900">Play track</h3>
        </div>
        <p className="text-sm text-slate-500">
          Stream NVR recording (video + audio) for{" "}
          <span className="font-medium text-slate-800">{channelName}</span>
          . Times are Pakistan (UTC+5).
        </p>

        <div className="mt-5 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="track-start">Start datetime</Label>
              <Input
                id="track-start"
                type="datetime-local"
                className="mt-1.5"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                disabled={loading}
              />
            </div>
            <div>
              <Label htmlFor="track-duration">Duration (seconds)</Label>
              <Input
                id="track-duration"
                type="number"
                min={1}
                max={300}
                className="mt-1.5"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value) || 1)}
                disabled={loading}
              />
              <p className="mt-1 text-[11px] text-slate-400">Max 300 seconds</p>
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
            </p>
          )}

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-black">
            {streamUrl ? (
              <video
                ref={videoRef}
                key={streamUrl}
                className="aspect-video w-full bg-black"
                controls
                autoPlay
                playsInline
                src={streamUrl}
                onPlaying={() => setLoading(false)}
                onWaiting={() => setLoading(true)}
                onError={() => {
                  setLoading(false);
                  setError(
                    "Could not play NVR track. Check datetime has a recording, then retry."
                  );
                }}
                onEnded={() => setLoading(false)}
              />
            ) : (
              <div className="flex aspect-video items-center justify-center text-sm text-slate-400">
                Pick a time and press Play stream
              </div>
            )}
          </div>

          {loading && streamUrl && (
            <p className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Connecting to NVR track…
            </p>
          )}
        </div>
      </div>

      <DialogFooter className="gap-2">
        <Button type="button" variant="outline" onClick={handleClose}>
          Close
        </Button>
        <Button type="button" onClick={handlePlay} disabled={!canSubmit}>
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Starting…
            </>
          ) : (
            <>
              <Video className="h-4 w-4" />
              Play stream
            </>
          )}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
