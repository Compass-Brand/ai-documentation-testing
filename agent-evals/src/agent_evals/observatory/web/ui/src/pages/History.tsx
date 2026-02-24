import { useState, useMemo } from "react";
import { History as HistoryIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { useRuns, useCostTrend, useCompareRuns } from "../api/hooks";
import type { Run } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { AccessibleChart } from "../components/AccessibleChart";
import { StatusBadge } from "../components/StatusBadge";
import { FadeIn } from "../components/FadeIn";
import { shortId, formatRunDate } from "../lib/utils";
import { CHART_COLORS } from "../lib/chart-theme";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
);

const statusMap = {
  completed: "success",
  active: "active",
  failed: "error",
} as const;

const columns: ColumnDef<Run>[] = [
  {
    accessorKey: "run_id",
    header: "Run ID",
    cell: ({ getValue }) => {
      const id = getValue<string>();
      return (
        <code className="text-data text-brand-charcoal">{shortId(id)}</code>
      );
    },
  },
  { accessorKey: "run_type", header: "Type" },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ getValue }) => {
      const status = getValue<Run["status"]>();
      return (
        <StatusBadge
          status={statusMap[status]}
          label={status}
        />
      );
    },
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ getValue }) => formatRunDate(getValue<string>()),
  },
];

export function History() {
  useDocumentTitle("History");
  const { data: runs, isLoading: runsLoading } = useRuns();
  const { data: costTrend } = useCostTrend();
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set());

  const selectedIds = useMemo(
    () => [...selectedRunIds],
    [selectedRunIds],
  );

  const handleRowClick = (run: Run) => {
    setSelectedRunIds((prev) => {
      const next = new Set(prev);
      if (next.has(run.run_id)) {
        next.delete(run.run_id);
      } else {
        next.add(run.run_id);
      }
      return next;
    });
  };
  const { data: comparison } = useCompareRuns(selectedIds);

  // Cost trend chart data
  const trendData = Array.isArray(costTrend) ? costTrend : [];
  const lineData = {
    labels: trendData.map((r: { created_at: string }) =>
      formatRunDate(r.created_at),
    ),
    datasets: [
      {
        label: "Cost ($)",
        data: trendData.map((r: { total_cost: number }) => r.total_cost),
        borderColor: CHART_COLORS.primary,
        backgroundColor: `${CHART_COLORS.primary}26`,
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 3,
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

  if (runsLoading) {
    return (
      <div className="px-sp-6 py-sp-8">
        <p className="text-body text-brand-slate">Loading history...</p>
      </div>
    );
  }

  return (
    <div className="px-sp-6 py-sp-8 max-w-full 2xl:max-w-[1400px] mx-auto">
      <FadeIn>
        <h1 className="text-h2 text-brand-charcoal inline-flex items-center gap-sp-3 mb-sp-8">
          <HistoryIcon className="h-8 w-8 text-brand-goldenrod" />
          History
        </h1>
      </FadeIn>

      <FadeIn delay={1}>
        <Card className="mb-sp-8">
          <CardHeader>
            <CardTitle>Cost Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <AccessibleChart
              label="Cost trend across runs"
              summary={`Cost per run across ${trendData.length} completed runs`}
            >
              <div className="h-64">
                {trendData.length > 0 ? (
                  <Line data={lineData} options={lineOptions} />
                ) : (
                  <div className="flex h-full items-center justify-center text-brand-slate">
                    No completed runs yet.
                  </div>
                )}
              </div>
            </AccessibleChart>
          </CardContent>
        </Card>
      </FadeIn>

      <FadeIn delay={2}>
        <Card className="mb-sp-8">
          <CardHeader>
            <CardTitle>Select Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={columns}
              data={runs ?? []}
              selectedRowIds={selectedRunIds}
              getRowId={(run) => run.run_id}
              onRowClick={handleRowClick}
            />
          </CardContent>
        </Card>
      </FadeIn>

      <FadeIn delay={3}>
        <Card>
          <CardHeader>
            <CardTitle>Compare Runs</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedIds.length < 2 ? (
              <p className="text-body-sm text-brand-slate">
                Select 2 or more runs above to compare.
              </p>
            ) : comparison ? (
              <div className="overflow-x-auto">
                <table className="w-full text-body-sm">
                  <thead>
                    <tr className="border-b border-brand-mist text-left text-caption text-brand-slate">
                      <th className="px-sp-3 py-sp-2">Metric</th>
                      {comparison.map((r) => (
                        <th key={r.run?.run_id} className="px-sp-3 py-sp-2">
                          <code>{shortId(r.run?.run_id ?? "")}</code>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="text-brand-charcoal">
                    <tr className="border-b border-brand-mist/50">
                      <td className="px-sp-3 py-sp-2 text-brand-slate">Type</td>
                      {comparison.map((r) => (
                        <td key={r.run?.run_id} className="px-sp-3 py-sp-2">{r.run?.run_type}</td>
                      ))}
                    </tr>
                    <tr className="border-b border-brand-mist/50">
                      <td className="px-sp-3 py-sp-2 text-brand-slate">Mean Score</td>
                      {comparison.map((r) => (
                        <td key={r.run?.run_id} className="px-sp-3 py-sp-2 font-medium">
                          {(r.mean_score ?? 0).toFixed(3)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-brand-mist/50">
                      <td className="px-sp-3 py-sp-2 text-brand-slate">Trials</td>
                      {comparison.map((r) => (
                        <td key={r.run?.run_id} className="px-sp-3 py-sp-2">{r.total_trials}</td>
                      ))}
                    </tr>
                    <tr className="border-b border-brand-mist/50">
                      <td className="px-sp-3 py-sp-2 text-brand-slate">Cost</td>
                      {comparison.map((r) => (
                        <td key={r.run?.run_id} className="px-sp-3 py-sp-2">
                          ${(r.total_cost ?? 0).toFixed(2)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-sp-3 py-sp-2 text-brand-slate">Status</td>
                      {comparison.map((r) => (
                        <td key={r.run?.run_id} className="px-sp-3 py-sp-2">
                          <StatusBadge
                            status={statusMap[r.run?.status as keyof typeof statusMap] ?? "neutral"}
                            label={r.run?.status ?? "unknown"}
                          />
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-body-sm text-brand-slate">
                Loading comparison...
              </p>
            )}
          </CardContent>
        </Card>
      </FadeIn>
    </div>
  );
}
