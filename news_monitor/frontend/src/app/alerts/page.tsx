"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AlertsPageContent } from "@/components/alerts/alerts-page-content";
import { useMonitor } from "@/hooks/use-monitor";

export default function AlertsPage() {
  const monitor = useMonitor();

  return (
    <AppShell monitorRunning={monitor.running}>
      <AlertsPageContent />
    </AppShell>
  );
}
