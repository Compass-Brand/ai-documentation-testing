import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Radar } from "react-chartjs-2";
import { useRuns, useRun, useRunAnalysis } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Skeleton } from "../components/Skeleton";
import { EmptyState } from "../components/EmptyState";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { CHART_COLORS } from "../lib/chart-theme";
import { formatRunLabel } from "../lib/utils";
import { Select } from "../components/Select";
import { TabBar } from "../components/TabBar";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { ColumnDef } from "@tanstack/react-table";

Chart.register(
  CategoryScale,
  LinearScale,
  BarElement,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

interface VariantRow {
  name: string;
  mean_score: number;
  trial_count: number;
}

const variantColumns: ColumnDef<VariantRow>[] = [
  { accessorKey: "name", header: "Variant" },
  {
    accessorKey: "mean_score",
    header: "Mean Score",
    cell: ({ getValue }) => (getValue() as number).toFixed(2),
  },
  { accessorKey: "trial_count", header: "Trials" },
];

interface InlineAnovaRow {
  factor: string;
  p_value: number;
  omega_squared: number;
  significant: boolean;
}

const inlineAnovaColumns: ColumnDef<InlineAnovaRow>[] = [
  { accessorKey: "factor", header: "Factor" },
  {
    accessorKey: "p_value",
    header: "p-value",
    cell: ({ getValue }) => (getValue() as number).toFixed(4),
  },
  {
    accessorKey: "omega_squared",
    header: "\u03C9\u00B2",
    cell: ({ getValue }) => (getValue() as number).toFixed(4),
  },
  {
    accessorKey: "significant",
    header: "Significance",
    cell: ({ getValue }) =>
      getValue() ? (
        <StatusBadge status="success" label="Significant" />
      ) : (
        <StatusBadge status="neutral" label="Not significant" />
      ),
  },
];

export function ResultsExplorer() {
  useDocumentTitle("Results");
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "analysis">(
    "overview",
  );
  const { data: runs } = useRuns();
  const { data: summary, isLoading } = useRun(runId ?? null);
  const { data: analysis } = useRunAnalysis(runId ?? null);

  const variantRows: VariantRow[] = summary
    ? Object.entries(summary.by_variant ?? {}).map(([name, v]) => ({
        name,
        mean_score: v.mean_score,
        trial_count: v.trial_count,
      }))
    : [];

  const barData = {
    labels: variantRows.map((r) => r.name),
    datasets: [
      {
        label: "Mean Score",
        data: variantRows.map((r) => r.mean_score),
        backgroundColor: CHART_COLORS.primary,
        borderRadius: 4,
      },
    ],
  };

  const barOptions = {
    indexAxis: "y" as const,
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: { min: 0, max: 1, title: { display: true, text: "Score" } },
    },
  };

  const modelEntries = summary?.by_model
    ? Object.entries(summary.by_model ?? {})
    : [];

  const radarData = {
    labels: ["Score", "Trials", "Cost"],
    datasets: modelEntries.map(([model, data], i) => ({
      label: model,
      data: [data.mean_score, data.trial_count / 100, data.cost / 10],
      borderColor: i === 0 ? CHART_COLORS.primary : CHART_COLORS.secondary,
      backgroundColor:
        i === 0 ? `${CHART_COLORS.primary}26` : `${CHART_COLORS.secondary}26`,
    })),
  };

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-8 flex items-center justify-between">
          <h1 className="flex items-center gap-sp-3 text-h2 text-brand-charcoal">
            <BarChart3 className="h-8 w-8 text-brand-goldenrod" />
            Results Explorer
          </h1>
          <div className="w-64">
            <Select
              aria-label="Select run"
              value={runId ?? ""}
              onValueChange={(v) => navigate(`/results/${v}`)}
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
      </FadeIn>

      {!runId && !isLoading && (
        <EmptyState
          icon={BarChart3}
          title="No Run Selected"
          description="Select a run to view results, or check the history page."
          ctaLabel="View History"
          ctaTo="/history"
        />
      )}

      {isLoading && (
        <div>
          <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} variant="card" />
            ))}
          </div>
          <Skeleton variant="chart" className="mb-sp-8" />
          <Skeleton variant="card" />
        </div>
      )}

      {summary && (
        <>
          {analysis && (
            <FadeIn>
              <div className="mb-sp-6">
                <TabBar
                  tabs={[
                    { key: "overview", label: "Overview" },
                    { key: "analysis", label: "Factor Analysis" },
                  ]}
                  activeKey={activeTab}
                  onTabChange={(key) => setActiveTab(key as "overview" | "analysis")}
                />
              </div>
            </FadeIn>
          )}

          {activeTab === "overview" && (
            <>
              <FadeIn delay={1}>
                <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
                  <Card variant="stat">
                    <CardHeader>
                      <CardTitle>Total Trials</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <span className="text-h2 text-brand-charcoal">
                        <AnimatedNumber value={summary.total_trials} format={(n) => String(Math.round(n))} />
                      </span>
                    </CardContent>
                  </Card>
                  <Card variant="stat">
                    <CardHeader>
                      <CardTitle>Mean Score</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <span className="text-h2 text-brand-charcoal">
                        <AnimatedNumber value={summary.mean_score ?? 0} format={(n) => n.toFixed(2)} />
                      </span>
                    </CardContent>
                  </Card>
                  <Card variant="stat">
                    <CardHeader>
                      <CardTitle>Total Cost</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <span className="text-h2 text-brand-charcoal">
                        <AnimatedNumber value={summary.total_cost} format={(n) => `$${n.toFixed(2)}`} />
                      </span>
                    </CardContent>
                  </Card>
                </div>
              </FadeIn>

              <FadeIn delay={2}>
                <Card className="mb-sp-8">
                  <CardHeader>
                    <CardTitle>Variant Scores</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AccessibleChart
                      label="Variant scores bar chart"
                      summary={`Bar chart showing scores for ${variantRows.length} variants`}
                    >
                      <Bar data={barData} options={barOptions} />
                    </AccessibleChart>
                  </CardContent>
                </Card>
              </FadeIn>

              {modelEntries.length > 0 && (
                <FadeIn delay={3}>
                  <Card className="mb-sp-8">
                    <CardHeader>
                      <CardTitle>Model Comparison</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <AccessibleChart
                        label="Model comparison radar chart"
                        summary={`Radar chart comparing ${modelEntries.length} models`}
                      >
                        <Radar data={radarData} />
                      </AccessibleChart>
                    </CardContent>
                  </Card>
                </FadeIn>
              )}

              <FadeIn delay={4}>
                <Card>
                  <CardHeader>
                    <CardTitle>Variant Breakdown</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DataTable columns={variantColumns} data={variantRows} />
                  </CardContent>
                </Card>
              </FadeIn>
            </>
          )}

          {activeTab === "analysis" && analysis && (
            <>
              <FadeIn delay={1}>
                <Card className="mb-sp-8">
                  <CardHeader>
                    <CardTitle>ANOVA Summary</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DataTable
                      columns={inlineAnovaColumns}
                      data={Object.entries(analysis.anova).map(
                        ([factor, stats]) => ({
                          factor,
                          p_value: stats.p_value,
                          omega_squared: stats.omega_squared,
                          significant:
                            analysis.significant_factors.includes(factor),
                        }),
                      )}
                    />
                  </CardContent>
                </Card>
              </FadeIn>

              <FadeIn delay={2}>
                <Card>
                  <CardHeader>
                    <CardTitle>Optimal Configuration</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2 md:grid-cols-3">
                      {Object.entries(analysis.optimal).map(
                        ([factor, level]) => (
                          <div
                            key={factor}
                            className="rounded-card border border-brand-mist p-sp-4"
                          >
                            <p className="text-caption text-brand-slate">
                              {factor}
                            </p>
                            <p className="text-h4 text-brand-charcoal">
                              {level}
                            </p>
                            {analysis.significant_factors.includes(factor) && (
                              <StatusBadge
                                status="success"
                                label="Significant"
                                className="mt-sp-2"
                              />
                            )}
                          </div>
                        ),
                      )}
                    </div>
                  </CardContent>
                </Card>
              </FadeIn>
            </>
          )}
        </>
      )}
    </div>
  );
}
