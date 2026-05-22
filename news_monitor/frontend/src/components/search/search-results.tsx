"use client";

import { FileSearch, Inbox } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SectionCard } from "@/components/ui/section-card";
import { Badge } from "@/components/ui/badge";
import { ExtractionItem } from "@/components/dashboard/extraction-item";
import { TranscriptionItem } from "@/components/dashboard/transcription-item";
import type { AudioTranscription, TextExtraction } from "@/lib/types";

interface SearchResultsProps {
  textResults: TextExtraction[];
  audioResults: AudioTranscription[];
  textCount: number;
  audioCount: number;
  query: string;
}

export function SearchResults({
  textResults,
  audioResults,
  textCount,
  audioCount,
  query,
}: SearchResultsProps) {
  const total = textCount + audioCount;

  return (
    <SectionCard
      title="Search Results"
      icon={<FileSearch className="h-5 w-5 text-primary" />}
      accent="primary"
      headerExtra={
        <Badge variant="default">{total} results</Badge>
      }
    >
      {query && (
        <p className="mb-4 text-sm text-slate-500">
          Query: <span className="urdu-text font-medium text-slate-800">{query}</span>
        </p>
      )}
      <Tabs defaultValue="text">
        <TabsList>
          <TabsTrigger value="text">Text ({textCount})</TabsTrigger>
          <TabsTrigger value="audio">Audio ({audioCount})</TabsTrigger>
        </TabsList>
        <TabsContent value="text" className="scroll-panel max-h-[640px]">
          {textResults.length === 0 ? (
            <EmptyState message="No text results. Enter a query and search." />
          ) : (
            textResults.map((r) => <ExtractionItem key={r.uuid} item={r} />)
          )}
        </TabsContent>
        <TabsContent value="audio" className="scroll-panel max-h-[640px]">
          {audioResults.length === 0 ? (
            <EmptyState message="No audio results for this query." />
          ) : (
            audioResults.map((r) => (
              <TranscriptionItem key={r.uuid} item={r} />
            ))
          )}
        </TabsContent>
      </Tabs>
    </SectionCard>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <Inbox className="mb-4 h-14 w-14 text-slate-300" />
      <p className="max-w-xs text-sm text-slate-500">{message}</p>
    </div>
  );
}
