import { AlertTriangle, XCircle } from "lucide-react";

export interface AlertItem {
  type: string;
  message: string;
  timestamp: Date;
}

interface AlertsFeedProps {
  alerts: AlertItem[];
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function AlertsFeed({ alerts }: AlertsFeedProps) {
  if (alerts.length === 0) {
    return (
      <p className="text-body-sm text-brand-slate">No alerts.</p>
    );
  }

  return (
    <div
      className="max-h-[250px] space-y-sp-2 overflow-y-auto"
      role="log"
      aria-label="Alerts feed"
    >
      {alerts.map((alert, i) => {
        const isError = alert.type === "model_budget_exceeded";
        return (
          <div
            key={`${alert.type}-${i}`}
            className={`flex items-start gap-sp-2 rounded-card px-sp-3 py-sp-2 text-body-sm ${
              isError ? "bg-brand-clay/5" : "bg-brand-amber/5"
            }`}
          >
            {isError ? (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-brand-clay" />
            ) : (
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-brand-amber" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-brand-charcoal">{alert.message}</p>
              <p className="text-caption text-brand-slate">
                {formatTime(alert.timestamp)}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
