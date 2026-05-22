"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Tv } from "lucide-react";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";
import { ConnectionIndicator } from "@/components/layout/connection-indicator";

interface NavbarProps {
  monitorRunning?: boolean;
  connected?: boolean | null;
}

export function Navbar({ monitorRunning = false, connected = null }: NavbarProps) {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-[#F1F5F9] bg-white/90 shadow-sm backdrop-blur-[12px]">
      <div className="mx-auto grid h-[60px] max-w-[1400px] grid-cols-[1fr_auto_1fr] items-center px-4 lg:px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 transition-opacity hover:opacity-85"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#1E40AF]">
            <Tv className="h-5 w-5" strokeWidth={2.5} />
          </span>
          <span className="text-[1.2rem] font-extrabold text-[#0F172A]">
            {siteConfig.name}
          </span>
        </Link>

        <ul className="flex items-center gap-0.5">
          {siteConfig.nav.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "relative px-4 py-4 text-sm font-medium transition-colors duration-150",
                    active
                      ? "text-[#1E40AF]"
                      : "text-slate-500 hover:text-[#1E40AF]"
                  )}
                >
                  {item.label}
                  {active && (
                    <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-[#1E40AF]" />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-end gap-3">
          <span
            className={cn(
              "hidden rounded-full px-3.5 py-1.5 text-xs font-medium sm:inline",
              monitorRunning
                ? "bg-[#F0FDF4] text-green-700"
                : "bg-[#F8FAFC] text-slate-500"
            )}
          >
            {monitorRunning ? "فعال" : "غیر فعال"}
          </span>
          <ConnectionIndicator connected={connected} />
        </div>
      </div>
    </nav>
  );
}
