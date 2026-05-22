"use client";

import { AppShell } from "@/components/layout/app-shell";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { useMonitor } from "@/hooks/use-monitor";

export default function SettingsPage() {
  const monitor = useMonitor();

  return (
    <AppShell monitorRunning={monitor.running}>
      <SettingsPanel />
    </AppShell>
  );
}
