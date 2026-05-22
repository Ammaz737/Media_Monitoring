"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
}

export function Dialog({ open, onOpenChange, children, className }: DialogProps) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center px-4 py-10 sm:py-14">
      <button
        type="button"
        className="fixed inset-0 bg-black/40 backdrop-blur-[4px]"
        aria-label="Close"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 max-h-[calc(100vh-5.5rem)] w-full max-w-[640px] overflow-y-auto rounded-2xl bg-white p-8 shadow-2xl sm:max-h-[calc(100vh-7rem)]",
          "transition-all duration-200 ease-out",
          className
        )}
        style={{
          animation: "dialogIn 200ms ease-out forwards",
        }}
      >
        <Button
          variant="ghost"
          size="icon"
          className="absolute end-4 top-4 text-slate-500"
          onClick={() => onOpenChange(false)}
        >
          <X className="h-5 w-5" />
        </Button>
        {children}
      </div>
    </div>
  );
}

export function DialogFooter({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mt-6 flex justify-end sm:justify-end", className)}>
      {children}
    </div>
  );
}
