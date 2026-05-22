"use client";

import { Loader2, LayoutList } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertStickyCard,
  ExtractionStickyCard,
  TranscriptionStickyCard,
} from "@/components/dashboard/activity-sticky-cards";
import type { Alert, AudioTranscription, TextExtraction } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ActivityTabsProps {
  extractions: TextExtraction[];
  transcriptions: AudioTranscription[];
  alerts: Alert[];
  loading?: boolean;
  onMarkAlertRead?: (uuid: string) => void;
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-500">
      <Loader2 className="mb-3 h-8 w-8 animate-spin text-primary" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <p className="py-16 text-center text-sm text-slate-500">{message}</p>
  );
}

function ActivityCardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {children}
    </div>
  );
}

export function ActivityTabs({
  extractions,
  transcriptions,
  alerts,
  loading,
  onMarkAlertRead,
}: ActivityTabsProps) {
  return (
    <Card className="dashboard-stagger-in overflow-hidden rounded-[20px] border border-[#F1F5F9] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)]" style={{ animationDelay: "250ms" }}>
      <div className="border-b border-slate-100 bg-white px-6 py-4">
        <h3 className="flex items-center gap-2 text-base font-bold text-slate-900">
          <LayoutList className="h-5 w-5 text-primary" />
          Recent Activity
        </h3>
      </div>
      <Tabs defaultValue="extractions" className="px-6 pb-6">
        <TabsList className="mt-4 h-auto w-full justify-start gap-1 rounded-xl bg-[#F8FAFC] p-1">
          <TabsTrigger
            value="extractions"
            className={cn(
              "rounded-[10px] px-5 py-2 text-sm font-medium text-slate-500 transition-all duration-150",
              "data-[state=active]:bg-[#1E40AF] data-[state=active]:font-semibold data-[state=active]:text-white data-[state=active]:shadow-sm"
            )}
          >
            Text Extractions
          </TabsTrigger>
          <TabsTrigger
            value="transcriptions"
            className={cn(
              "rounded-[10px] px-5 py-2 text-sm font-medium text-slate-500 transition-all duration-150",
              "data-[state=active]:bg-[#1E40AF] data-[state=active]:font-semibold data-[state=active]:text-white data-[state=active]:shadow-sm"
            )}
          >
            Audio Transcriptions
          </TabsTrigger>
          <TabsTrigger
            value="alerts"
            className={cn(
              "rounded-[10px] px-5 py-2 text-sm font-medium text-slate-500 transition-all duration-150",
              "data-[state=active]:bg-[#1E40AF] data-[state=active]:font-semibold data-[state=active]:text-white data-[state=active]:shadow-sm"
            )}
          >
            Recent Alerts
          </TabsTrigger>
        </TabsList>

        {loading ? (
          <LoadingState label="Loading..." />
        ) : (
          <>
            <TabsContent
              value="extractions"
              className="tab-content-fade scroll-panel mt-2 max-h-[640px]"
            >
              {extractions.length === 0 ? (
                <EmptyState message="No recent extractions" />
              ) : (
                <ActivityCardGrid>
                  {extractions.map((e) => (
                    <ExtractionStickyCard key={e.uuid} item={e} />
                  ))}
                </ActivityCardGrid>
              )}
            </TabsContent>
            <TabsContent
              value="transcriptions"
              className="tab-content-fade scroll-panel mt-2 max-h-[640px]"
            >
              {transcriptions.length === 0 ? (
                <EmptyState message="No recent transcriptions" />
              ) : (
                <ActivityCardGrid>
                  {transcriptions.map((t) => (
                    <TranscriptionStickyCard key={t.uuid} item={t} />
                  ))}
                </ActivityCardGrid>
              )}
            </TabsContent>
            <TabsContent
              value="alerts"
              className="tab-content-fade scroll-panel mt-2 max-h-[640px]"
            >
              {alerts.length === 0 ? (
                <EmptyState message="No recent alerts" />
              ) : (
                <ActivityCardGrid>
                  {alerts.map((a) => (
                    <AlertStickyCard
                      key={a.uuid}
                      item={a}
                      onMarkRead={onMarkAlertRead}
                    />
                  ))}
                </ActivityCardGrid>
              )}
            </TabsContent>
          </>
        )}
      </Tabs>
    </Card>
  );
}
