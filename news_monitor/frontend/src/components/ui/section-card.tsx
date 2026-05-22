import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface SectionCardProps {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  accent?: "primary" | "success" | "warning" | "rose" | "purple" | "teal";
  headerExtra?: React.ReactNode;
}

const accentBorder: Record<NonNullable<SectionCardProps["accent"]>, string> = {
  primary: "border-s-primary",
  success: "border-s-success",
  warning: "border-s-warning",
  rose: "border-s-rose",
  purple: "border-s-purple-500",
  teal: "border-s-teal-500",
};

export function SectionCard({
  title,
  icon,
  children,
  className,
  contentClassName,
  accent = "primary",
  headerExtra,
}: SectionCardProps) {
  return (
    <Card className={cn("premium-card overflow-hidden", className)}>
      <div
        className={cn(
          "flex items-center justify-between border-s-4 bg-white px-5 py-4",
          accentBorder[accent]
        )}
      >
        <h3 className="section-heading">
          {icon}
          {title}
        </h3>
        {headerExtra}
      </div>
      <CardContent className={cn("px-5 pb-5 pt-4", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}
