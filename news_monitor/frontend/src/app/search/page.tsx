"use client";

import { useCallback, useEffect, useState } from "react";
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
    fuzzy_threshold: searchParams.get("fuzzy_threshold") ?? "0.35",
  });
  const [textResults, setTextResults] = useState<TextExtraction[]>([]);
  const [audioResults, setAudioResults] = useState<AudioTranscription[]>([]);
  const [textCount, setTextCount] = useState(0);
  const [audioCount, setAudioCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const runSearch = useCallback(async (nextFilters?: SearchFilters) => {
    const active = nextFilters ?? filters;
    setLoading(true);
    try {
      const params = {
        q: active.q || undefined,
        start_date: active.start_date || undefined,
        end_date: active.end_date
          ? `${active.end_date}T23:59:59`
          : undefined,
        channel: active.channel || undefined,
        region: active.region || undefined,
        fuzzy_threshold: active.fuzzy_threshold
          ? parseFloat(active.fuzzy_threshold)
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
  }, [filters]);

  // Auto-load recent results on first visit
  useEffect(() => {
    void runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
            onSubmit={() => runSearch()}
            loading={loading}
          />
        </div>
      </div>
    </AppShell>
  );
}
