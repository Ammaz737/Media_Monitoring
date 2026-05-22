"use client";

import { useEffect, useRef, useState } from "react";
import { Globe, Hash, Link2, Mail, Plus, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn, hasArabicScript } from "@/lib/utils";

interface AlertKeywordsCardProps {
  keywords: string[];
  newKeyword: string;
  onNewKeywordChange: (value: string) => void;
  onAddKeyword: () => void;
  onRemoveKeyword: (kw: string) => void;
  notificationMethods: string[];
}

const METHOD_META: Record<
  string,
  { icon: typeof Globe; emoji: string; label: string }
> = {
  web: { icon: Globe, emoji: "🌐", label: "web" },
  email: { icon: Mail, emoji: "📧", label: "email" },
  webhook: { icon: Link2, emoji: "🔗", label: "webhook" },
};

function KeywordPill({
  keyword,
  onRemove,
  animateIn,
}: {
  keyword: string;
  onRemove: () => void;
  animateIn?: boolean;
}) {
  const isUrdu = hasArabicScript(keyword);
  const [visible, setVisible] = useState(!animateIn);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (animateIn) {
      const id = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(id);
    }
    setVisible(true);
  }, [animateIn]);

  const handleRemove = () => {
    setExiting(true);
    window.setTimeout(onRemove, 200);
  };

  return (
    <span
      role="listitem"
      dir={isUrdu ? "rtl" : "ltr"}
      className={cn(
        "inline-flex h-8 max-w-full items-center gap-2 rounded-full py-0 pl-3.5 pr-2 text-sm font-medium text-white shadow-[0_1px_3px_rgba(30,64,175,0.3)] transition-all duration-150 ease-out",
        isUrdu
          ? "bg-gradient-to-br from-[#065F46] to-[#059669] shadow-[0_1px_3px_rgba(5,150,105,0.35)]"
          : "bg-gradient-to-br from-[#1E3A8A] to-[#2563EB]",
        visible && !exiting
          ? "scale-100 opacity-100"
          : "pointer-events-none scale-0 opacity-0",
        !exiting && visible && "hover:scale-105 hover:shadow-[0_2px_8px_rgba(30,64,175,0.35)]"
      )}
    >
      <span
        className={cn(
          "truncate leading-none",
          isUrdu ? "font-urdu text-[0.875rem] leading-snug" : "font-sans"
        )}
      >
        {keyword}
      </span>
      <button
        type="button"
        onClick={handleRemove}
        className="flex h-[18px] w-[18px] shrink-0 cursor-pointer items-center justify-center rounded-full border-0 bg-white/20 text-[10px] leading-none text-white transition-colors duration-150 hover:bg-white/40"
        aria-label={`Remove ${keyword}`}
      >
        <X className="h-2.5 w-2.5" strokeWidth={3} />
      </button>
    </span>
  );
}

export function AlertKeywordsCard({
  keywords,
  newKeyword,
  onNewKeywordChange,
  onAddKeyword,
  onRemoveKeyword,
  notificationMethods,
}: AlertKeywordsCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const prevKeywordsRef = useRef<string[]>(keywords);
  const [newlyAdded, setNewlyAdded] = useState<Set<string>>(new Set());

  useEffect(() => {
    const prev = prevKeywordsRef.current;
    const added = keywords.filter((k) => !prev.includes(k));
    if (added.length > 0) {
      setNewlyAdded(new Set(added));
      const t = window.setTimeout(() => setNewlyAdded(new Set()), 250);
      prevKeywordsRef.current = keywords;
      return () => window.clearTimeout(t);
    }
    prevKeywordsRef.current = keywords;
  }, [keywords]);

  const submitKeyword = () => {
    if (!newKeyword.trim()) return;
    onAddKeyword();
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitKeyword();
    }
  };

  const countLabel =
    keywords.length === 1 ? "1 keyword" : `${keywords.length} keywords`;

  return (
    <Card className="premium-card overflow-hidden border-s-4 border-s-primary font-sans">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
        <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
          <Hash className="h-5 w-5 shrink-0 text-primary" />
          Alert Keywords
        </h3>
        <span className="shrink-0 rounded-md bg-slate-100 px-2.5 py-1 text-[0.72rem] font-medium text-slate-500">
          {countLabel}
        </span>
      </div>

      <CardContent className="px-5 pb-5 pt-4">
        {keywords.length === 0 ? (
          <div className="mb-3 flex h-[60px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50">
            <p className="px-4 text-center text-sm text-slate-400">
              No keywords yet. Add your first keyword below.
            </p>
          </div>
        ) : (
          <div
            role="list"
            aria-label="Alert keywords"
            className="flex flex-wrap items-center gap-2 py-1 pb-3"
          >
            {keywords.map((kw) => (
              <KeywordPill
                key={kw}
                keyword={kw}
                animateIn={newlyAdded.has(kw)}
                onRemove={() => onRemoveKeyword(kw)}
              />
            ))}
          </div>
        )}

        <div className="flex items-center gap-2" dir="ltr">
          <button
            type="button"
            onClick={submitKeyword}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#1E40AF] text-white shadow-[0_2px_6px_rgba(30,64,175,0.35)] transition-all duration-150 hover:scale-105 hover:shadow-[0_3px_10px_rgba(30,64,175,0.4)] active:scale-[0.98]"
            aria-label="Add keyword"
          >
            <Plus className="h-5 w-5" strokeWidth={2.5} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={newKeyword}
            onChange={(e) => onNewKeywordChange(e.target.value)}
            onKeyDown={handleKeyDown}
            dir="auto"
            placeholder="Type keyword and press Enter..."
            className={cn(
              "h-10 min-w-0 flex-1 rounded-full border-[1.5px] border-[#E2E8F0] bg-white px-4 text-sm text-slate-900 outline-none transition-all duration-150",
              "placeholder:text-slate-400 focus:border-primary focus:shadow-[0_0_0_3px_rgba(30,64,175,0.1)]",
              hasArabicScript(newKeyword) && "font-urdu text-base leading-relaxed"
            )}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {notificationMethods.map((method) => {
            const meta = METHOD_META[method] ?? {
              icon: Globe,
              emoji: "•",
              label: method,
            };
            const Icon = meta.icon;
            return (
              <span
                key={method}
                className="inline-flex items-center gap-1 rounded-md bg-[#F1F5F9] px-2 py-[3px] text-[0.72rem] text-slate-500"
              >
                <span aria-hidden>{meta.emoji}</span>
                <Icon className="h-3 w-3 opacity-60" />
                {meta.label}
              </span>
            );
          })}
        </div>

        <p className="mt-2 text-[0.72rem] italic text-slate-400">
          UI-only until saved via backend config
        </p>
      </CardContent>
    </Card>
  );
}
