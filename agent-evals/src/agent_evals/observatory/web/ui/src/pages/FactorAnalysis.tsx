import { useParams } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import { useRunAnalysis } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { CHART_COLORS } from "../lib/chart-theme";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { ColumnDef } from "@tanstack/react-table";

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface AnovaRow {
  factor: string;
  ss: number;
  df: number;
  ms: number;
  f_ratio: number;
  p_value: number;
  omega_squared: number;
  significant: boolean;
}

const anovaColumns: ColumnDef<AnovaRow>[] = [
  { accessorKey: "factor", header: "Factor" },
  {
    accessorKey: "ss",
    header: "SS",
    cell: ({ getValue }) => (getValue() as number).toFixed(3),
  },
  { accessorKey: "df", header: "df" },
  {
    accessorKey: "ms",
    header: "MS",
    cell: ({ getValue }) => (getValue() as number).toFixed(3),
  },
  {
    accessorKey: "f_ratio",
    header: "F-ratio",
    cell: ({ getValue }) => (getValue() as number).toFixed(2),
  },
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

const LEVEL_COLORS = [
  CHART_COLORS.primary,
  CHART_COLORS.secondary,
  CHART_COLORS.success,
  CHART_COLORS.warning,
  CHART_COLORS.error,
];

export function FactorAnalysis() {
  useDocumentTitle("Factor Analysis");
  const { runId } = useParams<{ runId: string }>();
  const { data: analysis, isLoading } = useRunAnalysis(runId ?? null);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
        <p className="text-body text-brand-slate">Loading...</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
        <p className="text-body text-brand-slate">
          No analysis data available.
        </p>
      </div>
    );
  }

  const factors = Object.keys(analysis.main_effects);
  const allLevels = Array.from(
    new Set(factors.flatMap((f) => Object.keys(analysis.main_effects[f]))),
  );

  const barData = {
    labels: factors,
    datasets: allLevels.map((level, i) => ({
      label: level,
      data: factors.map((f) => analysis.main_effects[f][level] ?? 0),
      backgroundColor: LEVEL_COLORS[i % LEVEL_COLORS.length],
      borderRadius: 4,
    })),
  };

  const barOptions = {
    responsive: true,
    plugins: {
      legend: { display: true },
    },
    scales: {
      y: {
        title: { display: true, text: "S/N Ratio (dB)" },
      },
    },
  };

  const anovaRows: AnovaRow[] = Object.entries(analysis.anova).map(
    ([factor, stats]) => ({
      factor,
      ss: stats.ss,
      df: stats.df,
      ms: stats.ms,
      f_ratio: stats.f_ratio,
      p_value: stats.p_value,
      omega_squared: stats.omega_squared,
      significant: analysis.significant_factors.includes(factor),
    }),
  );

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-8 flex items-center justify-between">
          <h1 className="flex items-center gap-sp-3 text-h2 text-brand-charcoal">
            <FlaskConical className="h-8 w-8 text-brand-goldenrod" />
            Factor Analysis
          </h1>
          <span className="text-body-sm text-brand-slate">
            {analysis.quality_type.replace(/_/g, " ")}
          </span>
        </div>
      </FadeIn>

      <FadeIn delay={1}>
        <Card className="mb-sp-8">
          <CardHeader>
            <CardTitle>Main Effects</CardTitle>
          </CardHeader>
          <CardContent>
            <AccessibleChart
              label="Main effects bar chart"
              summary={`Bar chart showing S/N ratios for ${factors.length} factors`}
            >
              <Bar data={barData} options={barOptions} />
            </AccessibleChart>
          </CardContent>
        </Card>
      </FadeIn>

      <FadeIn delay={2}>
        <Card className="mb-sp-8">
          <CardHeader>
            <CardTitle>ANOVA Results</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable columns={anovaColumns} data={anovaRows} />
          </CardContent>
        </Card>
      </FadeIn>

      <FadeIn delay={3}>
        <Card>
          <CardHeader>
            <CardTitle>Optimal Prediction</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-sp-4 sm:grid-cols-2 md:grid-cols-3">
              {Object.entries(analysis.optimal).map(([factor, level]) => (
                <div
                  key={factor}
                  className="rounded-card border border-brand-mist p-sp-4"
                >
                  <p className="text-caption text-brand-slate">{factor}</p>
                  <p className="text-h4 text-brand-charcoal">{level}</p>
                  {analysis.significant_factors.includes(factor) && (
                    <StatusBadge
                      status="success"
                      label="Significant"
                      className="mt-sp-2"
                    />
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </FadeIn>
    </div>
  );
}
