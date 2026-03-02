import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Loader2, CheckCircle } from "lucide-react";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { FadeIn } from "../components/FadeIn";
import { cn } from "../lib/utils";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useStartRun, useActiveRuns, useDatasets } from "../api/hooks";
import type { StartRunPayload } from "../api/client";

type RunMode = "taguchi" | "full";

export default function RunConfig() {
  useDocumentTitle("Run Config");
  const navigate = useNavigate();
  const startRun = useStartRun();
  const activeRuns = useActiveRuns();
  const [mode, setMode] = useState<RunMode>("taguchi");
  const [model, setModel] = useState("");
  const [repetitions, setRepetitions] = useState(3);
  const [taskLimit, setTaskLimit] = useState(0);
  const [oaOverride, setOaOverride] = useState("");
  const [pipelineMode, setPipelineMode] = useState<"auto" | "semi">("auto");
  const [qualityType, setQualityType] = useState("larger_is_better");
  const [topK, setTopK] = useState(3);
  const [alpha, setAlpha] = useState(0.05);
  const [source, setSource] = useState("gold_standard");
  const datasets = useDatasets();
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(false);

  const activeCount = activeRuns.data?.count ?? 0;
  const isSubmitting = startRun.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!model.trim()) {
      setError("Model is required");
      return;
    }

    const payload: StartRunPayload = {
      mode,
      model: model.trim(),
      repetitions,
      task_limit: taskLimit,
      source,
    };

    if (oaOverride) payload.oa_override = oaOverride;
    if (mode === "taguchi") {
      payload.pipeline_mode = pipelineMode;
      payload.quality_type = qualityType;
      payload.top_k = topK;
      payload.alpha = alpha;
    }

    startRun.mutate(payload, {
      onSuccess: (data) => {
        navigate(`/live?run_id=${data.run_id}`);
      },
      onError: (err) => {
        setError(err.message || "Failed to start evaluation");
        setCooldown(true);
        setTimeout(() => setCooldown(false), 1500);
      },
    });
  }

  return (
    <div className="mx-auto max-w-wide px-sp-6 py-sp-8">
      <FadeIn>
        <div className="mb-sp-8 flex items-center gap-sp-3">
          <Play className="h-6 w-6 text-brand-goldenrod" />
          <h1 className="text-h2 text-brand-charcoal">Run Configuration</h1>
        </div>
      </FadeIn>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-sp-8 lg:grid-cols-2">
          {/* Left column: Mode + Model */}
          <FadeIn delay={1}>
            <Card>
              <CardContent>
                <fieldset>
                  <legend className="mb-sp-4 text-h5 text-brand-charcoal">
                    Evaluation Mode
                  </legend>
                  <div className="grid grid-cols-2 gap-sp-4">
                    {(["taguchi", "full"] as const).map((m) => (
                      <label
                        key={m}
                        className={cn(
                          "relative flex cursor-pointer flex-col items-center gap-sp-2",
                          "rounded-card border-2 p-sp-6 transition-all duration-micro",
                          mode === m
                            ? "border-brand-goldenrod bg-brand-goldenrod/8"
                            : "border-brand-mist hover:border-brand-slate",
                        )}
                      >
                        {mode === m && (
                          <CheckCircle className="absolute right-sp-3 top-sp-3 h-5 w-5 text-brand-goldenrod" />
                        )}
                        <input
                          type="radio"
                          name="mode"
                          value={m}
                          checked={mode === m}
                          onChange={() => setMode(m)}
                          className="absolute inset-0 opacity-0 cursor-pointer"
                          aria-label={m === "taguchi" ? "Taguchi" : "Full"}
                        />
                        <span className="text-h5 font-medium capitalize text-brand-charcoal">
                          {m === "taguchi" ? "Taguchi" : "Full"}
                        </span>
                        <span className="text-caption text-brand-slate text-center">
                          {m === "taguchi"
                            ? "Uses orthogonal arrays to test many factor combinations efficiently. Reduces trials from thousands to ~50 while identifying which documentation format choices matter most."
                            : "Tests every combination of variants. Comprehensive but expensive \u2014 use for small experiments or final validation."}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="mt-sp-6">
                  <label
                    htmlFor="model"
                    className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                  >
                    Model
                  </label>
                  <Input
                    id="model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="openrouter/anthropic/claude-sonnet-4"
                  />
                  <p className="mt-sp-1 text-caption text-brand-slate">
                    The LLM to evaluate against. Use OpenRouter format (e.g.
                    openrouter/anthropic/claude-sonnet-4). Separate multiple
                    models with commas.
                  </p>
                </div>

                <div className="mt-sp-6">
                  <label
                    htmlFor="source"
                    className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                  >
                    Task Source
                  </label>
                  <Select
                    aria-label="Task Source"
                    value={source}
                    onValueChange={setSource}
                    options={[
                      { value: "gold_standard", label: "Gold Standard (built-in)" },
                      ...(datasets.data ?? []).map((d) => ({
                        value: d.name,
                        label: d.name,
                      })),
                    ]}
                  />
                  <p className="mt-sp-1 text-caption text-brand-slate">
                    Choose which task dataset to evaluate against. Gold Standard
                    uses the built-in 355 tasks. External datasets must be
                    prepared first.
                  </p>
                </div>
              </CardContent>
            </Card>
          </FadeIn>

          {/* Right column: Parameters */}
          <FadeIn delay={2}>
            <Card>
              <CardContent>
                <h3 className="mb-sp-4 text-h5 text-brand-charcoal">
                  Parameters
                </h3>

                <div className="space-y-sp-5">
                  <div>
                    <label
                      htmlFor="repetitions"
                      className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                    >
                      Repetitions
                    </label>
                    <Input
                      id="repetitions"
                      type="number"
                      min={1}
                      max={10}
                      value={repetitions}
                      onChange={(e) =>
                        setRepetitions(parseInt(e.target.value) || 1)
                      }
                    />
                    <p className="mt-sp-1 text-caption text-brand-slate">
                      Number of times each trial is repeated for statistical
                      reliability. Higher = more reliable but more expensive.
                      Default: 3.
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="taskLimit"
                      className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                    >
                      Task Limit (0 = all)
                    </label>
                    <Input
                      id="taskLimit"
                      type="number"
                      min={0}
                      value={taskLimit}
                      onChange={(e) =>
                        setTaskLimit(parseInt(e.target.value) || 0)
                      }
                    />
                    <p className="mt-sp-1 text-caption text-brand-slate">
                      Limit the number of gold standard tasks to evaluate. Set
                      to 0 to use all 355 tasks. Useful for quick test runs.
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="oaOverride"
                      className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                    >
                      OA Override (optional)
                    </label>
                    <Input
                      id="oaOverride"
                      value={oaOverride}
                      onChange={(e) => setOaOverride(e.target.value)}
                      placeholder="e.g. L9_3_4"
                    />
                    <p className="mt-sp-1 text-caption text-brand-slate">
                      Force a specific orthogonal array (e.g. L9_3_4,
                      L27_3_13). Leave blank to auto-select based on factor
                      count.
                    </p>
                  </div>

                  {mode === "taguchi" && (
                    <>
                      <div>
                        <label
                          htmlFor="pipelineMode"
                          className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                        >
                          Pipeline Mode
                        </label>
                        <Select
                          aria-label="Pipeline Mode"
                          value={pipelineMode}
                          onValueChange={(v) =>
                            setPipelineMode(v as "auto" | "semi")
                          }
                          options={[
                            { value: "auto", label: "Auto (run all phases)" },
                            { value: "semi", label: "Semi (approve between phases)" },
                          ]}
                        />
                        <p className="mt-sp-1 text-caption text-brand-slate">
                          Auto runs all three phases automatically. Semi pauses
                          between phases for review.
                        </p>
                      </div>

                      <div>
                        <label
                          htmlFor="qualityType"
                          className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                        >
                          Quality Type
                        </label>
                        <Select
                          aria-label="Quality Type"
                          value={qualityType}
                          onValueChange={setQualityType}
                          options={[
                            { value: "larger_is_better", label: "Larger is Better" },
                            { value: "smaller_is_better", label: "Smaller is Better" },
                            { value: "nominal_is_best", label: "Nominal is Best" },
                          ]}
                        />
                        <p className="mt-sp-1 text-caption text-brand-slate">
                          How to optimize the signal-to-noise ratio. Larger is
                          Better: maximize scores. Smaller is Better: minimize
                          errors. Nominal is Best: hit a target value.
                        </p>
                      </div>

                      <div>
                        <label
                          htmlFor="topK"
                          className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                        >
                          Top-K Factors
                        </label>
                        <Input
                          id="topK"
                          type="number"
                          min={1}
                          max={10}
                          value={topK}
                          onChange={(e) =>
                            setTopK(parseInt(e.target.value) || 3)
                          }
                        />
                        <p className="mt-sp-1 text-caption text-brand-slate">
                          Number of most significant factors to carry into the
                          refinement phase. Default: 3.
                        </p>
                      </div>

                      <div>
                        <label
                          htmlFor="alpha"
                          className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                        >
                          Alpha (significance level)
                        </label>
                        <Input
                          id="alpha"
                          type="number"
                          min={0.001}
                          max={0.1}
                          step={0.001}
                          value={alpha}
                          onChange={(e) =>
                            setAlpha(parseFloat(e.target.value) || 0.05)
                          }
                        />
                        <p className="mt-sp-1 text-caption text-brand-slate">
                          Statistical significance threshold for ANOVA. Factors
                          with p-value below alpha are considered significant.
                          Default: 0.05 (95% confidence).
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          </FadeIn>
        </div>

        <FadeIn delay={3}>
          {error && (
            <div className="mt-sp-4 rounded-card border border-red-300 bg-red-50 px-sp-4 py-sp-3 text-body-sm text-red-700">
              {error}
            </div>
          )}

          {activeCount > 0 && (
            <div className="mt-sp-4 rounded-card border border-brand-goldenrod/30 bg-brand-goldenrod/5 px-sp-4 py-sp-3 text-body-sm text-brand-charcoal">
              {activeCount} {activeCount === 1 ? "run" : "runs"} currently in progress.
            </div>
          )}

          <div className="mt-sp-8 flex justify-end">
            <Button type="submit" size="lg" disabled={isSubmitting || cooldown}>
              {isSubmitting ? (
                <Loader2 className="mr-sp-2 h-5 w-5 animate-spin" />
              ) : (
                <Play className="mr-sp-2 h-5 w-5" />
              )}
              {isSubmitting ? "Starting..." : "Start Evaluation"}
            </Button>
          </div>
        </FadeIn>
      </form>
    </div>
  );
}
