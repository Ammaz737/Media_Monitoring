import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { getAuthToken, getFlaskDirectBase } from "@/lib/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** True when string contains Arabic/Urdu script (for font selection). */
export function hasArabicScript(text: string): boolean {
  return /[\u0600-\u06FF\u0750-\u077F]/.test(text);
}

export function formatRuntime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function formatTimestamp(ts: string, locale = "ur-PK"): string {
  try {
    return new Date(ts).toLocaleString(locale);
  } catch {
    return ts;
  }
}

export function parseKeywords(raw: string | string[] | null | undefined): string[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [String(parsed)];
  } catch {
    return [raw];
  }
}

function withAuthToken(url: string): string {
  const token = getAuthToken();
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

/** Build URL for a stored screenshot (basename from absolute/relative path). */
export function screenshotUrl(
  path: string | null | undefined
): string | null {
  if (!path) return null;
  const normalized = path.replace(/\\/g, "/");
  const filename = normalized.split("/").pop();
  if (!filename) return null;
  // Hit Flask directly — Next rewrite can break binary img responses
  return withAuthToken(
    `${getFlaskDirectBase()}/api/screenshots/${encodeURIComponent(filename)}`
  );
}

/** Build same-origin URL for a stored transcription WAV clip. */
export function transcriptionAudioUrl(
  path: string | null | undefined
): string | null {
  if (!path) return null;
  const normalized = path.replace(/\\/g, "/");
  const filename = normalized.split("/").pop();
  if (!filename) return null;
  return withAuthToken(
    `/api/transcriptions/audio/${encodeURIComponent(filename)}`
  );
}
