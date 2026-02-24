import { useParams, useNavigate, Link } from "react-router-dom";
import { GitBranch } from "lucide-react";
import { usePipeline, usePipelines } from "../api/hooks";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { FadeIn } from "../components/FadeIn";
import { StatusBadge } from "../components/StatusBadge";
import { cn, shortId } from "../lib/utils";
import { Select } from "../components/Select";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import type { Run } from "../api/client";

const PHASE_ORDER = ["screening", "confirmation", "refinement"] as const;

const PHASE_DESCRIPTIONS: Record<string, string> = {
  screening:
    "Taguchi OA to identify significant factors with minimal trials.",
  confirmation:
    "Validates the optimal configuration found during screening.",
  refinement:
    "Full factorial on significant factors for fine-tuning.",
};

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
  useDocumentTitle("Pipeline");
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const navigate = useNavigate();
  const { data: pipelines } = usePipelines();
  const { data: pipeline, isLoading } = usePipeline(pipelineId ?? null);

  const noPipelines = !isLoading && pipelines && pipelines.length === 0;

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-4 flex items-center justify-between">
          <h1 className="flex items-center gap-sp-3 text-h2 text-brand-charcoal">
            <GitBranch className="h-8 w-8 text-brand-goldenrod" />
            Pipeline View
          </h1>
          {!noPipelines && (
            <div className="w-64">
              <Select
                aria-label="Select pipeline"
                value={pipelineId ?? ""}
                onValueChange={(v) => navigate(`/pipeline/${v}`)}
                placeholder="Select a pipeline..."
                options={
                  pipelines?.map((p) => ({
                    value: p.pipeline_id,
                    label: `${shortId(p.pipeline_id)} (${p.run_count} ${p.run_count === 1 ? "run" : "runs"})`,
                  })) ?? []
                }
              />
            </div>
          )}
        </div>
        <p className="mb-sp-8 text-body-sm text-brand-slate">
          A DOE pipeline runs three phases: Screening (Taguchi OA to find
          significant factors) → Confirmation (validate optimal config) →
          Refinement (full factorial on top factors).
        </p>
      </FadeIn>

      {noPipelines && (
        <p className="text-body text-brand-slate">
          No pipelines yet. Run an evaluation with{" "}
          <code className="text-data text-brand-charcoal">--pipeline auto</code>{" "}
          to create one.
        </p>
      )}

      {!pipelineId && !isLoading && !noPipelines && (
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
            <div className="flex flex-wrap items-stretch gap-sp-4">
              {pipeline.runs.map((run, index) => {
                const phase = inferPhase(run, index);
                const badgeStatus =
                  statusMap[run.status as keyof typeof statusMap] ?? "neutral";
                const description =
                  PHASE_DESCRIPTIONS[phase] ?? "";

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
                          {description && (
                            <p className="mb-sp-2 text-caption text-brand-slate">
                              {description}
                            </p>
                          )}
                          <p className="mb-sp-2 text-caption text-brand-slate">
                            <code className="text-data">{shortId(run.run_id)}</code>
                          </p>
                          <StatusBadge
                            status={badgeStatus}
                            label={run.status}
                          />
                        </CardContent>
                      </Card>
                    </Link>
                    {index < pipeline.runs.length - 1 && (
                      <svg
                        className="flex-shrink-0 self-center mx-sp-2"
                        width="40"
                        height="24"
                        viewBox="0 0 40 24"
                        aria-hidden="true"
                      >
                        <line
                          x1="0"
                          y1="12"
                          x2="30"
                          y2="12"
                          stroke={run.status === "completed" || run.status === "active" ? "#C2A676" : "#5C6B7F"}
                          strokeWidth="2"
                          strokeDasharray={run.status === "completed" || run.status === "active" ? "none" : "4 3"}
                        />
                        <polygon
                          points="30,6 40,12 30,18"
                          fill={run.status === "completed" || run.status === "active" ? "#C2A676" : "#5C6B7F"}
                        />
                      </svg>
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
