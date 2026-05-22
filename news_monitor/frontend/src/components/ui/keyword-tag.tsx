"use client";

import { cn, hasArabicScript } from "@/lib/utils";

interface KeywordTagProps {
  keyword: string;
  className?: string;
}

/** Square keyword tag — enough height for Urdu without clipping */
export function KeywordTag({ keyword, className }: KeywordTagProps) {
  const urdu = hasArabicScript(keyword);
  return (
    <span
      dir={urdu ? "rtl" : "ltr"}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-3 text-[0.78rem] font-semibold text-white",
        urdu
          ? "keyword-tag-urdu min-h-[36px] bg-[#065F46] py-1.5"
          : "min-h-[28px] bg-[#1E40AF] py-1.5 font-sans",
        className
      )}
    >
      {keyword}
    </span>
  );
}
