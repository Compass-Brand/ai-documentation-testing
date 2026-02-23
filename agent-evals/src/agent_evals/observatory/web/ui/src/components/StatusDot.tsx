const dotColors = {
  success: "bg-brand-sage",
  warning: "bg-brand-amber animate-pulse",
  error: "bg-brand-clay",
  syncing: "bg-brand-amber animate-pulse",
  offline: "bg-brand-slate",
} as const;

type DotStatus = keyof typeof dotColors;

export function StatusDot({ status }: { status: DotStatus }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${dotColors[status]}`}
      role="status"
      aria-label={status}
    />
  );
}
