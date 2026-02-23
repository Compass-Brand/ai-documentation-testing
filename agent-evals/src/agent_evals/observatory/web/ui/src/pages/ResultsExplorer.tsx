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
import { useRuns, useRun } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";
import { DataTable } from "../components/DataTable";
import { CHART_COLORS } from "../lib/chart-theme";
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

export function ResultsExplorer() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: runs } = useRuns();
  const { data: summary, isLoading } = useRun(runId ?? null);

  const variantRows: VariantRow[] = summary
    ? Object.entries(summary.by_variant).map(([name, v]) => ({
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
    ? Object.entries(summary.by_model)
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
          <label className="flex items-center gap-sp-3 text-body-sm text-brand-slate">
            <span className="sr-only">Select run</span>
            <select
              aria-label="Select run"
              role="combobox"
              value={runId ?? ""}
              onChange={(e) => navigate(`/results/${e.target.value}`)}
              className="h-11 rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2 text-body-sm text-brand-charcoal"
            >
              <option value="">Select a run...</option>
              {runs?.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.run_type})
                </option>
              ))}
            </select>
          </label>
        </div>
      </FadeIn>

      {!runId && !isLoading && (
        <p className="text-body text-brand-slate">
          Select a run to view results.
        </p>
      )}

      {isLoading && (
        <p className="text-body text-brand-slate">Loading...</p>
      )}

      {summary && (
        <>
          <FadeIn delay={1}>
            <div className="mb-sp-8 grid grid-cols-1 gap-sp-6 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>Total Trials</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    {summary.total_trials}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Mean Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    {summary.mean_score.toFixed(2)}
                  </span>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Total Cost</CardTitle>
                </CardHeader>
                <CardContent>
                  <span className="text-h2 text-brand-charcoal">
                    ${summary.total_cost.toFixed(2)}
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
    </div>
  );
}
