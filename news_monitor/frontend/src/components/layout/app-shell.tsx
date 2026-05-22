"use client";

import { Navbar } from "@/components/layout/navbar";

interface AppShellProps {
  children: React.ReactNode;
  monitorRunning?: boolean;
  connected?: boolean | null;
}

export function AppShell({
  children,
  monitorRunning,
  connected = null,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Navbar monitorRunning={monitorRunning} connected={connected} />
      <main className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 lg:px-6">
        {children}
      </main>
    </div>
  );
}
