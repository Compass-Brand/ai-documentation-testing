import { Component, useMemo, type ErrorInfo, type ReactNode } from "react";
import {
  Activity,
  DollarSign,
  Zap,
  AlertCircle,
  Clock,
  Hash,
  BarChart3,
} from "lucide-react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip as ChartTooltip,
} from "chart.js";
import { useLiveMonitorState } from "../hooks/useLiveMonitorState";
import { RunSelector } from "../components/RunSelector";
import { ModelBreakdown } from "../components/ModelBreakdown";
import { VariantSummary } from "../components/VariantSummary";
import { AlertsFeed } from "../components/AlertsFeed";
import { EmptyState } from "../components/EmptyState";
import { Card, CardContent, CardTitle } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { Skeleton } from "../components/Skeleton";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { Tooltip } from "../components/Tooltip";
import { LastUpdated } from "../components/LastUpdated";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { cn } from "../lib/utils";
import { CHART_COLORS } from "../lib/chart-theme";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  ChartTooltip,
);

class LiveMonitorErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("LiveMonitor error:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto max-w-wide px-sp-6 py-sp-8 text-center">
          <AlertCircle className="mx-auto mb-sp-3 h-8 w-8 text-brand-clay" />
          <h2 className="text-h4 text-brand-charcoal">Something went wrong</h2>
          <p className="text-body-sm text-brand-slate mt-sp-2">
            {this.state.error?.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function LiveMonitor() {
  return (
    <LiveMonitorErrorBoundary>
      <LiveMonitorContent />
    </LiveMonitorErrorBoundary>
  );
}

function LiveMonitorContent() {
  useDocumentTitle("Live Monitor");
  const state = useLiveMonitorState();

  const chartData = useMemo(
    () => ({
      labels: state.scores.map((_, i) => String(i + 1)),
      datasets: [
        {
          label: "Score",
          data: state.scores,
          borderColor: CHART_COLORS.primary,
          backgroundColor: `${CHART_COLORS.primary}26`,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    }),
    [state.scores],
  );

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: { min: 0, max: 1, grid: { color: CHART_COLORS.grid } },
      x: { grid: { display: false } },
    },
    plugins: { legend: { display: false } },
  } as const;

  if (state.isLoading) {
    return (
      <div className="space-y-sp-6 p-sp-6">
        <div className="grid grid-cols-2 gap-sp-4 md:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="card" />
          ))}
        </div>
        <Skeleton variant="chart" />
      </div>
    );
  }

  if (!state.selectedRunId) {
    return (
      <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
        <EmptyState
          icon={Activity}
          title="No Active Runs"
          description="Start an evaluation to see live monitoring results."
          ctaLabel="Start Evaluation"
          ctaTo="/"
        />
      </div>
    );
  }

  const etaLabel =
    state.estimatedRemainingMinutes != null
      ? `~${Math.ceil(state.estimatedRemainingMinutes)}m left`
      : "";

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      {/* Header */}
      <FadeIn>
        <div className="mb-sp-6 flex flex-wrap items-center gap-sp-3">
          <Activity className="h-6 w-6 text-brand-goldenrod" />
          <h1 className="text-h2 text-brand-charcoal">Live Monitor</h1>
          <div className="ml-auto flex items-center gap-sp-4">
            <RunSelector
              selectedRunId={state.selectedRunId}
              onSelectRun={state.setSelectedRunId}
            />
            <LastUpdated timestamp={state.lastUpdated} />
            {state.isConnected && (
              <span className="inline-flex items-center gap-sp-1 text-body-sm text-brand-amber">
                <span className="h-2 w-2 rounded-full bg-brand-amber animate-pulse" />
                Live
              </span>
            )}
          </div>
        </div>
      </FadeIn>

      {/* Progress bar */}
      <FadeIn delay={1}>
        <div className="mb-sp-8">
          <div className="mb-sp-2 flex flex-wrap justify-between gap-sp-2 text-body-sm text-brand-slate">
            <span>
              {state.trialsCompleted} / {state.trialsTotal} trials
            </span>
            <span>
              {state.uniqueTasksSeen} / {state.totalTasks} tasks
            </span>
            <span className="flex items-center gap-sp-2">
              <span>{state.progress.toFixed(0)}%</span>
              {etaLabel && (
                <span className="text-caption">{etaLabel}</span>
              )}
            </span>
          </div>
          <div className="h-3 overflow-hidden rounded-pill bg-brand-mist">
            <div
              className={cn(
                "h-full rounded-pill bg-brand-goldenrod transition-all duration-state",
                state.isConnected && "animate-shimmer",
              )}
              style={{ width: `${state.progress}%` }}
            />
          </div>
        </div>
      </FadeIn>

      {/* Stat cards - 6 columns */}
      <FadeIn delay={2}>
        <div className="mb-sp-8 grid grid-cols-2 gap-sp-4 md:grid-cols-3 lg:grid-cols-6">
          <StatCard
            icon={<BarChart3 className="h-5 w-5" />}
            label="Score"
            tooltip="Average score across all completed trials"
            value={state.meanScore}
            format={(n) => n.toFixed(2)}
          />
          <StatCard
            icon={<DollarSign className="h-5 w-5" />}
            label="Cost"
            tooltip="Total API cost for this evaluation run"
            value={state.totalCost}
            format={(n) => "$" + n.toFixed(2)}
          />
          <StatCard
            icon={<Zap className="h-5 w-5" />}
            label="T/min"
            tooltip="Current throughput in trials per minute"
            value={state.trialsPerMin}
            format={(n) => n.toFixed(1)}
          />
          <StatCard
            icon={<Hash className="h-5 w-5" />}
            label="Tokens"
            tooltip="Total tokens consumed (prompt + completion)"
            value={state.totalTokens}
            format={formatTokens}
          />
          <StatCard
            icon={<Clock className="h-5 w-5" />}
            label="Latency"
            tooltip="Average response time per trial"
            value={state.avgLatency}
            format={(n) => n.toFixed(1) + "s"}
          />
          <StatCard
            icon={<AlertCircle className="h-5 w-5" />}
            label="Errors"
            tooltip="Number of trials that returned errors"
            value={state.errorCount}
            format={(n) => String(n)}
            variant={state.errorCount > 0 ? "error" : "default"}
          />
        </div>
      </FadeIn>

      {/* Score trend + Alerts */}
      <div className="mb-sp-8 grid gap-sp-8 lg:grid-cols-3">
        <FadeIn delay={3}>
          <Card className="lg:col-span-2">
            <CardContent>
              <CardTitle className="mb-sp-4">Score Trend</CardTitle>
              <div className="h-[250px]">
                {state.scores.length > 0 ? (
                  <Line data={chartData} options={chartOptions} />
                ) : (
                  <div className="flex h-full items-center justify-center text-body-sm text-brand-slate">
                    Waiting for trial results...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </FadeIn>

        <FadeIn delay={4}>
          <Card>
            <CardContent>
              <CardTitle className="mb-sp-4">Alerts</CardTitle>
              <AlertsFeed alerts={state.alerts} />
            </CardContent>
          </Card>
        </FadeIn>
      </div>

      {/* Model Breakdown + Variant Summary */}
      <div className="grid gap-sp-8 lg:grid-cols-2">
        <FadeIn delay={5}>
          <Card>
            <CardContent>
              <CardTitle className="mb-sp-4">Per-Model Breakdown</CardTitle>
              <ModelBreakdown data={state.byModel} />
            </CardContent>
          </Card>
        </FadeIn>

        <FadeIn delay={6}>
          <Card>
            <CardContent>
              <CardTitle className="mb-sp-4">Variant Summary</CardTitle>
              <VariantSummary data={state.byVariant} />
            </CardContent>
          </Card>
        </FadeIn>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  tooltip,
  value,
  format,
  variant = "default",
}: {
  icon: React.ReactNode;
  label: string;
  tooltip: string;
  value: number;
  format?: (n: number) => string;
  variant?: "default" | "error";
}) {
  return (
    <Tooltip content={tooltip}>
      <div>
        <Card variant="stat">
          <CardContent>
            <div className="flex items-center gap-sp-3">
              <span
                className={cn(
                  "text-brand-goldenrod",
                  variant === "error" && "text-brand-clay",
                )}
              >
                {icon}
              </span>
              <div>
                <p className="text-caption text-brand-slate">{label}</p>
                <p className="text-h4 font-medium text-brand-charcoal">
                  <AnimatedNumber value={value} format={format} />
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Tooltip>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return String(n);
}
