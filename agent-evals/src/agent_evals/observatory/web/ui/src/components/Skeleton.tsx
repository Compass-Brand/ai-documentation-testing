import { cn } from "../lib/utils";

type SkeletonVariant = "text" | "card" | "chart" | "circle";

interface SkeletonProps {
  variant?: SkeletonVariant;
  className?: string;
}

const variantClasses: Record<SkeletonVariant, string> = {
  text: "h-4 w-full rounded",
  card: "h-32 w-full rounded-card",
  chart: "h-64 w-full rounded-card",
  circle: "h-10 w-10 rounded-full",
};

export function Skeleton({ variant = "text", className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "bg-brand-mist shimmer",
        variantClasses[variant],
        className,
      )}
    />
  );
}
