import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Loader2 } from "lucide-react";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { FadeIn } from "../components/FadeIn";
import { cn } from "../lib/utils";
import { useStartRun, useActiveRun } from "../api/hooks";
import type { StartRunPayload } from "../api/client";

type RunMode = "taguchi" | "full";

export default function RunConfig() {
  const navigate = useNavigate();
  const startRun = useStartRun();
  const activeRun = useActiveRun();
  const [mode, setMode] = useState<RunMode>("taguchi");
  const [model, setModel] = useState("");
  const [repetitions, setRepetitions] = useState(3);
  const [taskLimit, setTaskLimit] = useState(0);
  const [oaOverride, setOaOverride] = useState("");
  const [pipelineMode, setPipelineMode] = useState<"auto" | "semi">("auto");
  const [qualityType, setQualityType] = useState("larger_is_better");
  const [topK, setTopK] = useState(3);
  const [alpha, setAlpha] = useState(0.05);
  const [error, setError] = useState<string | null>(null);

  const isRunActive = activeRun.data?.active === true;
  const isSubmitting = startRun.isPending;
  const isDisabled = isSubmitting || isRunActive;

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
                          "flex cursor-pointer flex-col items-center gap-sp-2",
                          "rounded-card border-2 p-sp-6 transition-all duration-micro",
                          mode === m
                            ? "border-brand-goldenrod bg-brand-goldenrod/5"
                            : "border-brand-mist hover:border-brand-slate",
                        )}
                      >
                        <input
                          type="radio"
                          name="mode"
                          value={m}
                          checked={mode === m}
                          onChange={() => setMode(m)}
                          className="sr-only"
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
                        <select
                          id="pipelineMode"
                          aria-label="Pipeline Mode"
                          value={pipelineMode}
                          onChange={(e) =>
                            setPipelineMode(
                              e.target.value as "auto" | "semi",
                            )
                          }
                          className="h-11 w-full rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2 text-body-sm text-brand-charcoal"
                        >
                          <option value="auto">
                            Auto (run all phases)
                          </option>
                          <option value="semi">
                            Semi (approve between phases)
                          </option>
                        </select>
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
                        <select
                          id="qualityType"
                          aria-label="Quality Type"
                          value={qualityType}
                          onChange={(e) => setQualityType(e.target.value)}
                          className="h-11 w-full rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2 text-body-sm text-brand-charcoal"
                        >
                          <option value="larger_is_better">
                            Larger is Better
                          </option>
                          <option value="smaller_is_better">
                            Smaller is Better
                          </option>
                          <option value="nominal_is_best">
                            Nominal is Best
                          </option>
                        </select>
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

          {isRunActive && (
            <div className="mt-sp-4 rounded-card border border-brand-goldenrod/30 bg-brand-goldenrod/5 px-sp-4 py-sp-3 text-body-sm text-brand-charcoal">
              A run is already in progress. Wait for it to complete or cancel it from the Live Monitor.
            </div>
          )}

          <div className="mt-sp-8 flex justify-end">
            <Button type="submit" size="lg" disabled={isDisabled}>
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
