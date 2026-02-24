import type { ReactNode } from "react";

interface AccessibleChartProps {
  label: string;
  summary: string;
  children: ReactNode;
}

export function AccessibleChart({
  label,
  summary,
  children,
}: AccessibleChartProps) {
  return (
    <div role="img" aria-label={label}>
      <span className="sr-only">{summary}</span>
      {children}
    </div>
  );
}
