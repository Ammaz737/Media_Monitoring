"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import {
  SearchForm,
  type SearchFilters,
} from "@/components/search/search-form";
import { SearchResults } from "@/components/search/search-results";
import { api } from "@/lib/api";
import { useMonitor } from "@/hooks/use-monitor";
import type { AudioTranscription, TextExtraction } from "@/lib/types";

export default function SearchPage() {
  const searchParams = useSearchParams();
  const monitor = useMonitor();
  const [filters, setFilters] = useState<SearchFilters>({
    q: searchParams.get("q") ?? "",
    start_date: searchParams.get("start_date") ?? "",
    end_date: searchParams.get("end_date") ?? "",
    channel: searchParams.get("channel") ?? "",
    region: searchParams.get("region") ?? "",
    min_confidence: searchParams.get("min_confidence") ?? "",
  });
  const [textResults, setTextResults] = useState<TextExtraction[]>([]);
  const [audioResults, setAudioResults] = useState<AudioTranscription[]>([]);
  const [textCount, setTextCount] = useState(0);
  const [audioCount, setAudioCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const runSearch = async () => {
    setLoading(true);
    try {
      const params = {
        q: filters.q || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date
          ? `${filters.end_date}T23:59:59`
          : undefined,
        channel: filters.channel || undefined,
        region: filters.region || undefined,
        min_confidence: filters.min_confidence
          ? parseFloat(filters.min_confidence)
          : undefined,
      };
      const [text, audio] = await Promise.all([
        api.searchText(params),
        api.searchAudio(params),
      ]);
      setTextResults(text.results);
      setTextCount(text.count);
      setAudioResults(audio.results);
      setAudioCount(audio.count);
    } catch {
      setTextResults([]);
      setAudioResults([]);
      setTextCount(0);
      setAudioCount(0);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell monitorRunning={monitor.running}>
      <div className="grid gap-6 lg:grid-cols-12 lg:items-start">
        <div className="lg:col-span-8">
          <SearchResults
            textResults={textResults}
            audioResults={audioResults}
            textCount={textCount}
            audioCount={audioCount}
            query={filters.q}
          />
        </div>
        <div className="lg:col-span-4">
          <SearchForm
            filters={filters}
            onChange={setFilters}
            onSubmit={runSearch}
            loading={loading}
          />
        </div>
      </div>
    </AppShell>
  );
}
