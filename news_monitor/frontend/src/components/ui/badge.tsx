import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 font-sans text-xs font-semibold capitalize transition-all duration-150",
  {
    variants: {
      variant: {
        default: "bg-primary text-white",
        secondary: "bg-slate-100 text-slate-600",
        success: "bg-success-light text-success",
        warning: "bg-warning-light text-warning",
        danger: "bg-rose-light text-rose",
        outline: "border border-slate-200 text-slate-700 bg-white",
        keyword: "bg-primary text-white gap-1 pr-1",
        channel: "bg-slate-100 text-slate-700",
        high: "bg-rose-light text-rose",
        medium: "bg-warning-light text-warning",
        low: "bg-success-light text-success",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
