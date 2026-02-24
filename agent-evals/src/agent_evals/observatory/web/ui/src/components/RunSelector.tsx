import { useActiveRuns } from "../api/hooks";
import { StatusDot } from "./StatusDot";
import { cn } from "../lib/utils";

interface RunSelectorProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}

export function RunSelector({ selectedRunId, onSelectRun }: RunSelectorProps) {
  const { data } = useActiveRuns();
  const runs = data?.runs ?? [];

  if (runs.length === 0) return null;

  if (runs.length === 1) {
    const run = runs[0];
    return (
      <div className="flex items-center gap-sp-2">
        <StatusDot status="success" />
        <span className="text-body-sm text-brand-charcoal font-medium">
          {run.mode}
        </span>
        <span className="text-caption text-brand-slate">
          {run.run_id.slice(0, 8)}
        </span>
      </div>
    );
  }

  return (
    <div className="flex gap-sp-1 rounded-pill bg-brand-mist p-sp-1" role="tablist">
      {runs.map((run) => {
        const isSelected = run.run_id === selectedRunId;
        return (
          <button
            key={run.run_id}
            role="tab"
            aria-selected={isSelected}
            onClick={() => onSelectRun(run.run_id)}
            className={cn(
              "flex items-center gap-sp-2 rounded-pill px-sp-3 py-sp-1",
              "text-body-sm transition-colors duration-micro",
              isSelected
                ? "bg-brand-bone text-brand-charcoal shadow-sm font-medium"
                : "text-brand-slate hover:text-brand-charcoal",
            )}
          >
            <StatusDot status="success" />
            <span>{run.mode}</span>
            <span className="text-caption">{run.run_id.slice(0, 8)}</span>
          </button>
        );
      })}
    </div>
  );
}
