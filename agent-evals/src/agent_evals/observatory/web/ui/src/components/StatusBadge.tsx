import { cn } from "../lib/utils";

type Status = "success" | "warning" | "error" | "neutral" | "active" | "new";

const statusStyles: Record<Status, string> = {
  success: "bg-brand-sage/15 text-brand-sage",
  warning: "bg-brand-amber/15 text-brand-amber",
  error: "bg-brand-clay/15 text-brand-clay",
  neutral: "bg-brand-slate/15 text-brand-slate",
  active: "bg-brand-goldenrod/15 text-brand-goldenrod",
  new: "bg-brand-goldenrod text-brand-charcoal",
};

interface StatusBadgeProps {
  status: Status;
  label: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill px-sp-3 py-sp-1",
        "text-caption font-medium",
        statusStyles[status],
        className,
      )}
    >
      {label}
    </span>
  );
}
