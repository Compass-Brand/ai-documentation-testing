import { useState, useMemo } from "react";
import { History as HistoryIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { useRuns, useCostTrend, useCompareRuns } from "../api/hooks";
import type { Run } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { AccessibleChart } from "../components/AccessibleChart";
import { StatusBadge } from "../components/StatusBadge";
import { FadeIn } from "../components/FadeIn";
import { shortId, formatRunDate } from "../lib/utils";

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
  const { data: runs, isLoading: runsLoading } = useRuns();
  const { data: costTrend } = useCostTrend();
  const [selectedRuns, setSelectedRuns] = useState<Run[]>([]);

  const selectedIds = useMemo(
    () => selectedRuns.map((r) => r.run_id),
    [selectedRuns],
  );
  const { data: comparison } = useCompareRuns(selectedIds);

  if (runsLoading) {
    return (
      <div className="px-sp-6 py-sp-8">
        <p className="text-body text-brand-slate">Loading history...</p>
      </div>
    );
  }

  return (
    <div className="px-sp-6 py-sp-8 max-w-full mx-auto">
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
              summary={
                costTrend
                  ? `Cost trend data with ${Object.keys(costTrend).length} data points`
                  : "Cost trend chart loading"
              }
            >
              <div className="h-64 flex items-center justify-center text-brand-slate">
                {costTrend
                  ? "Chart.js line chart renders here"
                  : "No cost data available"}
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
              selectable
              onSelectionChange={setSelectedRuns}
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
              <pre className="text-data text-brand-charcoal whitespace-pre-wrap">
                {JSON.stringify(comparison, null, 2)}
              </pre>
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
