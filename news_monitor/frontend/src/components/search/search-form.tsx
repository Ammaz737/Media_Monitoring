"use client";

import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { SectionCard } from "@/components/ui/section-card";

export interface SearchFilters {
  q: string;
  start_date: string;
  end_date: string;
  channel: string;
  region: string;
  min_confidence: string;
}

interface SearchFormProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
  onSubmit: () => void;
  loading?: boolean;
}

export function SearchForm({
  filters,
  onChange,
  onSubmit,
  loading,
}: SearchFormProps) {
  const set = (key: keyof SearchFilters, value: string) =>
    onChange({ ...filters, [key]: value });

  const confidenceVal = filters.min_confidence
    ? parseFloat(filters.min_confidence)
    : 0;

  return (
    <SectionCard
      title="Search"
      icon={<Search className="h-5 w-5 text-primary" />}
      accent="primary"
      className="lg:sticky lg:top-20"
    >
      <div className="space-y-5">
        <div>
          <Label htmlFor="q" className="text-slate-700">
            Query (Urdu or English)
          </Label>
          <div className="relative mt-1.5">
            <Search className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              id="q"
              className="urdu-text h-12 ps-10 text-base"
              placeholder="Search in Urdu or English..."
              value={filters.q}
              onChange={(e) => set("q", e.target.value)}
              dir="auto"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="start_date">Start Date</Label>
            <Input
              id="start_date"
              type="date"
              className="mt-1.5"
              value={filters.start_date}
              onChange={(e) => set("start_date", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="end_date">End Date</Label>
            <Input
              id="end_date"
              type="date"
              className="mt-1.5"
              value={filters.end_date}
              onChange={(e) => set("end_date", e.target.value)}
            />
          </div>
        </div>

        <div>
          <Label htmlFor="channel">Channel</Label>
          <Select
            id="channel"
            className="mt-1.5"
            value={filters.channel}
            onChange={(e) => set("channel", e.target.value)}
          >
            <option value="">All channels</option>
            <option value="news_channel">news_channel</option>
            <option value="channel_1">channel_1</option>
            <option value="channel_2">channel_2</option>
          </Select>
        </div>

        <div>
          <Label htmlFor="region">Region</Label>
          <Select
            id="region"
            className="mt-1.5"
            value={filters.region}
            onChange={(e) => set("region", e.target.value)}
          >
            <option value="">All regions</option>
            <option value="ticker">ticker</option>
            <option value="headline">headline</option>
            <option value="side_text">side_text</option>
          </Select>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <Label htmlFor="min_confidence">Min Confidence</Label>
            <span className="text-sm font-mono font-medium text-primary">
              {confidenceVal.toFixed(1)}
            </span>
          </div>
          <input
            id="min_confidence"
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={confidenceVal}
            onChange={(e) => set("min_confidence", e.target.value)}
            className="mt-2 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-primary"
          />
        </div>

        <Button className="w-full" size="lg" onClick={onSubmit} disabled={loading}>
          <Search className="h-4 w-4" />
          {loading ? "Searching..." : "Search"}
        </Button>
      </div>
    </SectionCard>
  );
}
