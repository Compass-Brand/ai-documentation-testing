import { useState } from "react";
import { Eye } from "lucide-react";
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Line, Doughnut } from "react-chartjs-2";
import { useRuns, useRun, useCostTrend } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";
import { CHART_COLORS } from "../lib/chart-theme";
import { formatRunLabel } from "../lib/utils";

Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
);

const MODEL_COLORS = [
  CHART_COLORS.primary,
  CHART_COLORS.secondary,
  CHART_COLORS.success,
  CHART_COLORS.warning,
  CHART_COLORS.error,
];

export function Observatory() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const activeRunId = selectedRunId ?? runs?.[0]?.run_id ?? null;
  const { data: summary, isLoading: summaryLoading } = useRun(activeRunId);
  const { data: costTrend, isLoading: trendLoading } = useCostTrend();

  const isLoading = runsLoading || summaryLoading || trendLoading;

  const costPerTrial =
    summary && summary.total_trials > 0
      ? (summary.total_cost ?? 0) / summary.total_trials
      : 0;

  const modelEntries = summary?.by_model
    ? Object.entries(summary.by_model ?? {})
    : [];

  // Cost trend chart data
  const trendRuns = (costTrend as { runs?: { run_id: string; cost: number; created_at: string }[] })?.runs ?? [];
  const lineData = {
    labels: trendRuns.map((r) =>
      new Date(r.created_at).toLocaleDateString(),
    ),
    datasets: [
      {
        label: "Cumulative Cost ($)",
        data: trendRuns.reduce<number[]>((acc, r) => {
          const prev = acc.length > 0 ? acc[acc.length - 1] : 0;
          acc.push(prev + r.cost);
          return acc;
        }, []),
        borderColor: CHART_COLORS.primary,
        backgroundColor: `${CHART_COLORS.primary}26`,
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 0,
      },
    ],
  };

  const lineOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { title: { display: true, text: "Cost ($)" } },
    },
  };

  // Doughnut chart data
  const doughnutData = {
    labels: modelEntries.map(([name]) => name),
    datasets: [
      {
        data: modelEntries.map(([, d]) => d.cost),
        backgroundColor: modelEntries.map(
          (_, i) => MODEL_COLORS[i % MODEL_COLORS.length],
        ),
        borderWidth: 0,
      },
    ],
  };

  const formatCurrency = (n: number) =>
    `$${n.toFixed(2)}`;

  const formatTokens = (n: number) =>
    n.toLocaleString();

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-8 flex items-center justify-between">
          <h1 className="flex items-center gap-sp-3 text-h2 text-brand-charcoal">
            <Eye className="h-8 w-8 text-brand-goldenrod" />
            Observatory
          </h1>
          <label className="flex items-center gap-sp-3 text-body-sm text-brand-slate">
            <span className="sr-only">Select run</span>
            <select
              aria-label="Select run"
              role="combobox"
              value={activeRunId ?? ""}
              onChange={(e) => setSelectedRunId(e.target.value || null)}
              className="h-11 rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2 text-body-sm text-brand-charcoal"
            >
              <option value="">Select a run...</option>
              {runs?.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {formatRunLabel(r)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </FadeIn>

      {isLoading && (
        <p className="text-body text-brand-slate">Loading...</p>
      )}

      {summary && (
        <>
          <FadeIn delay={1}>
            <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>Total Spend</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    {formatCurrency(summary.total_cost ?? 0)}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Total Tokens</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    {formatTokens(summary.total_tokens ?? 0)}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Cost / Trial</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    {formatCurrency(costPerTrial)}
                  </span>
                </CardContent>
              </Card>
            </div>
          </FadeIn>

          <FadeIn delay={2}>
            <Card className="mb-sp-8">
              <CardHeader>
                <CardTitle>Cost Burn</CardTitle>
              </CardHeader>
              <CardContent>
                <AccessibleChart
                  label="Cumulative cost burn chart"
                  summary={`Line chart showing cumulative cost across ${trendRuns.length} runs`}
                >
                  <Line data={lineData} options={lineOptions} />
                </AccessibleChart>
              </CardContent>
            </Card>
          </FadeIn>

          {modelEntries.length > 0 && (
            <FadeIn delay={3}>
              <Card>
                <CardHeader>
                  <CardTitle>Cost by Model</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="mx-auto max-w-[400px]">
                    <AccessibleChart
                      label="Cost by model doughnut chart"
                      summary={`Doughnut chart showing cost distribution across ${modelEntries.length} models`}
                    >
                      <Doughnut data={doughnutData} />
                    </AccessibleChart>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}
        </>
      )}
    </div>
  );
}
