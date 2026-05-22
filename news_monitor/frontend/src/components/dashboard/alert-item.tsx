"use client";

import { AlertCard } from "@/components/alerts/alert-card";
import type { Alert } from "@/lib/types";

interface AlertItemProps {
  item: Alert;
  onMarkRead?: (uuid: string) => void;
  variant?: "dashboard" | "page";
}

/** Compact alert card for dashboard & alerts page */
export function AlertItem({
  item,
  onMarkRead,
  variant = "dashboard",
}: AlertItemProps) {
  return (
    <div className={variant === "dashboard" ? "mb-3" : undefined}>
      <AlertCard item={item} onMarkRead={onMarkRead} />
    </div>
  );
}
