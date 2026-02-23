import { useState, useCallback, useMemo } from "react";
import { useParams } from "react-router-dom";
import {
  Activity,
  CheckCircle,
  AlertTriangle,
  DollarSign,
  Zap,
  AlertCircle,
} from "lucide-react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from "chart.js";
import { useRuns, useRun, useTrials } from "../api/hooks";
import { useSSE } from "../hooks/useSSE";
import { Card, CardContent, CardTitle } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { cn } from "../lib/utils";
import { CHART_COLORS } from "../lib/chart-theme";
import type { Trial } from "../api/client";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
);

export default function LiveMonitor() {
  const { runId: paramRunId } = useParams<{ runId: string }>();
  const { data: runs, isLoading: runsLoading } = useRuns();

  // Auto-detect most recent active run when no runId in URL
  const effectiveRunId = useMemo(() => {
    if (paramRunId) return paramRunId;
    if (!runs) return null;
    const activeRuns = runs
      .filter((r) => r.status === "active")
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    return activeRuns[0]?.run_id ?? null;
  }, [paramRunId, runs]);

  const { data: summary, isLoading } = useRun(effectiveRunId);
  const { data: trials } = useTrials(effectiveRunId);
  const [recentTrials, setRecentTrials] = useState<Trial[]>([]);
  const [scores, setScores] = useState<number[]>([]);

  const onTrialComplete = useCallback((trial: Trial) => {
    setRecentTrials((prev) => [trial, ...prev].slice(0, 50));
    setScores((prev) => [...prev, trial.score]);
  }, []);

  const onRunComplete = useCallback(() => {
    // Run finished — no special action needed, UI reflects final state
  }, []);

  useSSE({
    runId: effectiveRunId,
    onTrialComplete,
    onRunComplete,
  });

  // Derive stats
  const totalTrials = summary?.total_trials ?? 0;
  const completedTrials = summary?.completed_trials ?? 0;
  const progress = totalTrials > 0 ? (completedTrials / totalTrials) * 100 : 0;
  const meanScore = summary?.mean_score ?? 0;
  const totalCost = summary?.total_cost ?? 0;
  const errorCount = useMemo(
    () => (trials ?? []).filter((t) => t.error !== null).length,
    [trials],
  );
  const trialsPerMin = useMemo(() => {
    if (!summary?.run?.created_at || completedTrials === 0) return 0;
    const elapsed =
      (Date.now() - new Date(summary.run.created_at).getTime()) / 60000;
    return elapsed > 0 ? completedTrials / elapsed : 0;
  }, [summary, completedTrials]);

  // Chart data from accumulated scores
  const chartData = useMemo(
    () => ({
      labels: scores.map((_, i) => String(i + 1)),
      datasets: [
        {
          label: "Score",
          data: scores,
          borderColor: CHART_COLORS.primary,
          backgroundColor: `${CHART_COLORS.primary}26`, // 15% opacity
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    }),
    [scores],
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

  // Display list: recent SSE trials first, then fetched trials
  const displayTrials = recentTrials.length > 0 ? recentTrials : (trials ?? []).slice().reverse().slice(0, 20);

  if ((!paramRunId && runsLoading) || isLoading) {
    return (
      <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
        <p className="text-body text-brand-slate">Loading...</p>
      </div>
    );
  }

  if (!paramRunId && !effectiveRunId) {
    return (
      <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
        <div className="flex items-center gap-sp-3 mb-sp-6">
          <Activity className="h-6 w-6 text-brand-goldenrod" />
          <h1 className="text-h2 text-brand-charcoal">Live Monitor</h1>
        </div>
        <p className="text-body text-brand-slate">
          No active runs. Start an evaluation to see live results.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-6 flex items-center gap-sp-3">
          <Activity className="h-6 w-6 text-brand-goldenrod" />
          <h1 className="text-h2 text-brand-charcoal">Live Monitor</h1>
          {summary?.run?.status === "active" && (
            <span className="ml-sp-2 inline-flex items-center gap-sp-1 text-body-sm text-brand-amber">
              <span className="h-2 w-2 rounded-full bg-brand-amber animate-pulse" />
              Running
            </span>
          )}
        </div>
      </FadeIn>

      {/* Progress bar */}
      <FadeIn delay={1}>
        <div className="mb-sp-8">
          <div className="mb-sp-2 flex justify-between text-body-sm text-brand-slate">
            <span>
              {completedTrials} / {totalTrials} trials
            </span>
            <span>{progress.toFixed(0)}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-pill bg-brand-mist">
            <div
              className="h-full rounded-pill bg-brand-goldenrod transition-all duration-state"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </FadeIn>

      {/* Stat cards */}
      <FadeIn delay={2}>
        <div className="mb-sp-8 grid grid-cols-2 gap-sp-4 lg:grid-cols-4">
          <StatCard
            icon={<Activity className="h-5 w-5" />}
            label="Mean Score"
            value={meanScore.toFixed(2)}
          />
          <StatCard
            icon={<DollarSign className="h-5 w-5" />}
            label="Total Cost"
            value={`$${totalCost.toFixed(2)}`}
          />
          <StatCard
            icon={<Zap className="h-5 w-5" />}
            label="Trials/min"
            value={trialsPerMin.toFixed(1)}
          />
          <StatCard
            icon={<AlertCircle className="h-5 w-5" />}
            label="Errors"
            value={String(errorCount)}
            variant={errorCount > 0 ? "error" : "default"}
          />
        </div>
      </FadeIn>

      <div className="grid gap-sp-8 lg:grid-cols-3">
        {/* Score trend chart */}
        <FadeIn delay={3}>
          <Card className="lg:col-span-2">
            <CardContent>
              <CardTitle className="mb-sp-4">Score Trend</CardTitle>
              <div className="h-[250px]">
                {scores.length > 0 ? (
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

        {/* Recent trials feed */}
        <FadeIn delay={4}>
          <Card>
            <CardContent>
              <CardTitle className="mb-sp-4">Recent Trials</CardTitle>
              <div
                className="max-h-[250px] space-y-sp-2 overflow-y-auto"
                aria-live="polite"
              >
                {displayTrials.length === 0 ? (
                  <p className="text-body-sm text-brand-slate">
                    No trials yet.
                  </p>
                ) : (
                  displayTrials.map((trial, i) => (
                    <div
                      key={`${trial.task_id}-${trial.repetition}-${i}`}
                      className={cn(
                        "flex items-center gap-sp-3 rounded-card px-sp-3 py-sp-2",
                        "text-body-sm transition-colors duration-micro",
                        trial.error
                          ? "bg-brand-clay/5"
                          : "bg-brand-sage/5",
                      )}
                    >
                      {trial.error ? (
                        <AlertTriangle className="h-4 w-4 shrink-0 text-brand-clay" />
                      ) : (
                        <CheckCircle className="h-4 w-4 shrink-0 text-brand-sage" />
                      )}
                      <span className="truncate text-brand-charcoal">
                        {trial.task_id}
                      </span>
                      <span className="ml-auto shrink-0 font-medium text-brand-charcoal">
                        {trial.score.toFixed(2)}
                      </span>
                    </div>
                  ))
                )}
              </div>
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
  value,
  variant = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  variant?: "default" | "error";
}) {
  return (
    <Card>
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
            <p className="text-h4 font-medium text-brand-charcoal">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
