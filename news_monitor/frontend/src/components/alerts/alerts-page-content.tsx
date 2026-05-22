"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, Loader2, CheckCheck } from "lucide-react";
import { api } from "@/lib/api";
import { siteConfig } from "@/config/site";
import type { Alert } from "@/lib/types";
import { AlertCard } from "@/components/alerts/alert-card";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Filter = "all" | "unread" | "read";

export function AlertsPageContent() {
  const [filter, setFilter] = useState<Filter>("all");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: { limit: number; is_read?: boolean } = {
        limit: siteConfig.pagination.alertsPage,
      };
      if (filter === "unread") params.is_read = false;
      if (filter === "read") params.is_read = true;
      const res = await api.getAlerts(params);
      setAlerts(res.alerts);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const unreadCount = alerts.filter((a) => !a.is_read).length;
  const readCount = alerts.filter((a) => a.is_read).length;

  const markRead = async (uuid: string) => {
    try {
      await api.markAlertRead(uuid);
      setAlerts((prev) =>
        prev.map((a) => (a.uuid === uuid ? { ...a, is_read: true } : a))
      );
    } catch {
      /* ignore */
    }
  };

  const markAllRead = async () => {
    const unread = alerts.filter((a) => !a.is_read);
    await Promise.all(
      unread.map((a) => api.markAlertRead(a.uuid).catch(() => {}))
    );
    setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
  };

  const statBoxes: {
    key: Filter | "showing";
    label: string;
    value: number;
    filterTarget?: Filter;
  }[] = [
    { key: "showing", label: "Showing", value: alerts.length },
    {
      key: "unread",
      label: "Unread",
      value: unreadCount,
      filterTarget: "unread",
    },
    { key: "read", label: "Read", value: readCount, filterTarget: "read" },
  ];

  return (
    <div className="space-y-6 font-sans" dir="ltr">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-[#1E40AF] to-[#3B82F6] text-white shadow-lg">
            <Bell className="h-6 w-6" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Alerts
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              Keyword matches from monitored channels
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl"
          disabled={unreadCount === 0 || loading}
          onClick={markAllRead}
        >
          <CheckCheck className="h-4 w-4" />
          Mark All Read
        </Button>
      </div>

      {/* Stats */}
      <div className="grid max-w-2xl grid-cols-3 gap-4">
        {statBoxes.map(({ key, label, value, filterTarget }) => {
          const active =
            filterTarget !== undefined
              ? filter === filterTarget
              : filter === "all";
          const isUnreadStat = key === "unread";
          return (
            <button
              key={key}
              type="button"
              onClick={() =>
                filterTarget ? setFilter(filterTarget) : setFilter("all")
              }
              className={cn(
                "rounded-xl border px-6 py-3 text-center transition-all duration-150",
                isUnreadStat
                  ? "border-[#FDE68A] bg-[#FFFBEB]"
                  : "border-[#E2E8F0] bg-white",
                active &&
                  (isUnreadStat
                    ? "ring-2 ring-amber-300 ring-offset-1"
                    : "ring-2 ring-primary/30 ring-offset-1")
              )}
            >
              <p
                className={cn(
                  "text-[1.75rem] font-bold leading-none",
                  isUnreadStat ? "text-[#D97706]" : "text-[#1E293B]"
                )}
              >
                {value}
              </p>
              <p className="mt-1 text-[0.75rem] font-medium uppercase tracking-[0.08em] text-slate-400">
                {label}
              </p>
            </button>
          );
        })}
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2">
        {(
          [
            { id: "all" as const, label: "All" },
            { id: "unread" as const, label: "Unread", count: unreadCount },
            { id: "read" as const, label: "Read" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setFilter(tab.id)}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium transition-all duration-150",
              filter === tab.id
                ? "bg-[#1E40AF] text-white shadow-md"
                : "bg-[#F1F5F9] text-slate-600 hover:bg-slate-200"
            )}
          >
            {tab.label}
            {"count" in tab && tab.count > 0 && (
              <Badge
                variant="warning"
                className={cn(
                  "h-5 min-w-5 px-1.5 text-[10px]",
                  filter === tab.id && "bg-amber-200 text-amber-900"
                )}
              >
                {tab.count}
              </Badge>
            )}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-9 w-9 animate-spin text-primary" />
        </div>
      ) : alerts.length === 0 ? (
        <Card className="premium-card flex flex-col items-center justify-center py-24 text-center">
          <Bell className="mb-3 h-12 w-12 text-slate-300" />
          <p className="font-medium text-slate-600">No alerts found</p>
          <p className="mt-1 text-sm text-slate-400">
            Try another filter or start monitoring
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {alerts.map((a) => (
            <AlertCard
              key={a.uuid}
              item={a}
              onMarkRead={!a.is_read ? markRead : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
