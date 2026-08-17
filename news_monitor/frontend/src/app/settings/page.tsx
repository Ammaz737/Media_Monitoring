"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { useMonitor } from "@/hooks/use-monitor";
import { useAuth } from "@/components/auth/auth-provider";

export default function SettingsPage() {
  const monitor = useMonitor();
  const { can } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!can("configure")) router.replace("/");
  }, [can, router]);

  if (!can("configure")) return null;

  return (
    <AppShell monitorRunning={monitor.running}>
      <SettingsPanel />
    </AppShell>
  );
}
