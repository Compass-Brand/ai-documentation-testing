import { useParams, useNavigate, Link } from "react-router-dom";
import { GitBranch } from "lucide-react";
import { usePipeline, usePipelines } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { StatusBadge } from "../components/StatusBadge";
import { cn } from "../lib/utils";
import type { Run } from "../api/client";

const PHASE_ORDER = ["screening", "confirmation", "refinement"] as const;

const statusMap = {
  completed: "success",
  active: "active",
  failed: "error",
} as const;

function inferPhase(run: Run, index: number): string {
  const configPhase =
    typeof run.config?.phase === "string" ? run.config.phase : null;
  if (configPhase) return configPhase;
  return PHASE_ORDER[index] ?? `phase-${index + 1}`;
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function PipelineView() {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const navigate = useNavigate();
  const { data: pipelines } = usePipelines();
  const { data: pipeline, isLoading } = usePipeline(pipelineId ?? null);

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-8 flex items-center justify-between">
          <h1 className="flex items-center gap-sp-3 text-h2 text-brand-charcoal">
            <GitBranch className="h-8 w-8 text-brand-goldenrod" />
            Pipeline View
          </h1>
          <label className="flex items-center gap-sp-3 text-body-sm text-brand-slate">
            <span className="sr-only">Select pipeline</span>
            <select
              aria-label="Select pipeline"
              role="combobox"
              value={pipelineId ?? ""}
              onChange={(e) => navigate(`/pipeline/${e.target.value}`)}
              className="h-11 rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2 text-body-sm text-brand-charcoal"
            >
              <option value="">Select a pipeline...</option>
              {pipelines?.map((p) => (
                <option key={p.pipeline_id} value={p.pipeline_id}>
                  {p.pipeline_id}
                </option>
              ))}
            </select>
          </label>
        </div>
      </FadeIn>

      {!pipelineId && !isLoading && (
        <p className="text-body text-brand-slate">
          Select a pipeline to view its phases.
        </p>
      )}

      {isLoading && (
        <p className="text-body text-brand-slate">Loading...</p>
      )}

      {pipeline && (
        <>
          <FadeIn delay={1}>
            <p className="mb-sp-6 text-body-sm text-brand-slate">
              Pipeline:{" "}
              <span className="font-medium text-brand-charcoal">
                {pipeline.pipeline_id}
              </span>
            </p>
          </FadeIn>

          <FadeIn delay={2}>
            <div className="flex items-stretch gap-sp-4">
              {pipeline.runs.map((run, index) => {
                const phase = inferPhase(run, index);
                const badgeStatus =
                  statusMap[run.status as keyof typeof statusMap] ?? "neutral";

                return (
                  <div
                    key={run.run_id}
                    className="flex items-stretch"
                  >
                    <Link
                      to={`/results/${run.run_id}`}
                      className="block flex-1"
                    >
                      <Card
                        className={cn(
                          "min-w-[200px] cursor-pointer transition-all duration-micro",
                          "hover:ring-2 hover:ring-brand-goldenrod/30",
                        )}
                      >
                        <CardHeader>
                          <CardTitle>{capitalize(phase)}</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="mb-sp-2 text-caption text-brand-slate">
                            {run.run_id}
                          </p>
                          <StatusBadge
                            status={badgeStatus}
                            label={run.status}
                          />
                        </CardContent>
                      </Card>
                    </Link>
                    {index < pipeline.runs.length - 1 && (
                      <span
                        className="flex items-center px-sp-3 text-h3 text-brand-slate"
                        aria-hidden="true"
                      >
                        &rarr;
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </FadeIn>
        </>
      )}
    </div>
  );
}
