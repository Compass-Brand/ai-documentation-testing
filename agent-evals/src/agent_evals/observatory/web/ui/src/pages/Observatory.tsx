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
import { Skeleton } from "../components/Skeleton";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { LastUpdated } from "../components/LastUpdated";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";
import { CHART_COLORS } from "../lib/chart-theme";
import { formatRunLabel } from "../lib/utils";
import { Select } from "../components/Select";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

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
  useDocumentTitle("Observatory");
  const { data: runs, isLoading: runsLoading } = useRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const activeRunId = selectedRunId ?? runs?.[0]?.run_id ?? null;
  const { data: summary, isLoading: summaryLoading, dataUpdatedAt } = useRun(activeRunId);
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
          <div className="flex items-center gap-sp-4">
            <LastUpdated timestamp={dataUpdatedAt} />
            <div className="w-64">
              <Select
                aria-label="Select run"
                value={activeRunId ?? ""}
                onValueChange={(v) => setSelectedRunId(v || null)}
                placeholder="Select a run..."
                options={
                  runs?.map((r) => ({
                    value: r.run_id,
                    label: formatRunLabel(r),
                  })) ?? []
                }
              />
            </div>
          </div>
        </div>
      </FadeIn>

      {isLoading && (
        <div>
          <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} variant="card" />
            ))}
          </div>
          <Skeleton variant="chart" />
        </div>
      )}

      {summary && (
        <>
          <FadeIn delay={1}>
            <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
              <Card variant="stat">
                <CardHeader>
                  <CardTitle>Total Spend</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    <AnimatedNumber value={summary.total_cost ?? 0} format={formatCurrency} />
                  </span>
                </CardContent>
              </Card>
              <Card variant="stat">
                <CardHeader>
                  <CardTitle>Total Tokens</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    <AnimatedNumber value={summary.total_tokens ?? 0} format={formatTokens} />
                  </span>
                </CardContent>
              </Card>
              <Card variant="stat">
                <CardHeader>
                  <CardTitle>Cost / Trial</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    <AnimatedNumber value={costPerTrial} format={formatCurrency} />
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
