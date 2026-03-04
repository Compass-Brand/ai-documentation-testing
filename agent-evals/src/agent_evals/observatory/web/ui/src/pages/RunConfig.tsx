import { useReducer, useRef, useEffect } from "react";
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

interface FormState {
  mode: RunMode;
  model: string;
  repetitions: number;
  taskLimit: number;
  oaOverride: string;
  pipelineMode: "auto" | "semi";
  qualityType: string;
  topK: number;
  alpha: number;
  source: string;
  error: string | null;
  cooldown: boolean;
}

type FormAction =
  | { type: "SET_MODE"; payload: RunMode }
  | { type: "SET_MODEL"; payload: string }
  | { type: "SET_REPETITIONS"; payload: number }
  | { type: "SET_TASK_LIMIT"; payload: number }
  | { type: "SET_OA_OVERRIDE"; payload: string }
  | { type: "SET_PIPELINE_MODE"; payload: "auto" | "semi" }
  | { type: "SET_QUALITY_TYPE"; payload: string }
  | { type: "SET_TOP_K"; payload: number }
  | { type: "SET_ALPHA"; payload: number }
  | { type: "SET_SOURCE"; payload: string }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "SET_COOLDOWN"; payload: boolean };

const initialState: FormState = {
  mode: "taguchi",
  model: "",
  repetitions: 3,
  taskLimit: 0,
  oaOverride: "",
  pipelineMode: "auto",
  qualityType: "larger_is_better",
  topK: 3,
  alpha: 0.05,
  source: "gold_standard",
  error: null,
  cooldown: false,
};

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "SET_MODE":
      return { ...state, mode: action.payload };
    case "SET_MODEL":
      return { ...state, model: action.payload };
    case "SET_REPETITIONS":
      return { ...state, repetitions: action.payload };
    case "SET_TASK_LIMIT":
      return { ...state, taskLimit: action.payload };
    case "SET_OA_OVERRIDE":
      return { ...state, oaOverride: action.payload };
    case "SET_PIPELINE_MODE":
      return { ...state, pipelineMode: action.payload };
    case "SET_QUALITY_TYPE":
      return { ...state, qualityType: action.payload };
    case "SET_TOP_K":
      return { ...state, topK: action.payload };
    case "SET_ALPHA":
      return { ...state, alpha: action.payload };
    case "SET_SOURCE":
      return { ...state, source: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    case "SET_COOLDOWN":
      return { ...state, cooldown: action.payload };
  }
}

interface ModeSelectorProps {
  mode: RunMode;
  onModeChange: (mode: RunMode) => void;
}

function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
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
              onChange={() => onModeChange(m)}
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
  );
}

interface TaguchiParamsProps {
  pipelineMode: "auto" | "semi";
  qualityType: string;
  topK: number;
  alpha: number;
  dispatch: React.Dispatch<FormAction>;
}

function TaguchiParams({
  pipelineMode,
  qualityType,
  topK,
  alpha,
  dispatch,
}: TaguchiParamsProps) {
  return (
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
            dispatch({ type: "SET_PIPELINE_MODE", payload: v as "auto" | "semi" })
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
          onValueChange={(v) =>
            dispatch({ type: "SET_QUALITY_TYPE", payload: v })
          }
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
            dispatch({ type: "SET_TOP_K", payload: parseInt(e.target.value) || 3 })
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
            dispatch({ type: "SET_ALPHA", payload: parseFloat(e.target.value) || 0.05 })
          }
        />
        <p className="mt-sp-1 text-caption text-brand-slate">
          Statistical significance threshold for ANOVA. Factors
          with p-value below alpha are considered significant.
          Default: 0.05 (95% confidence).
        </p>
      </div>
    </>
  );
}

export default function RunConfig() {
  useDocumentTitle("Run Config");
  const navigate = useNavigate();
  const startRun = useStartRun();
  const activeRuns = useActiveRuns();
  const [state, dispatch] = useReducer(formReducer, initialState);
  const datasets = useDatasets();
  const cooldownTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    return () => clearTimeout(cooldownTimer.current);
  }, []);

  const activeCount = activeRuns.data?.count ?? 0;
  const isSubmitting = startRun.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    dispatch({ type: "SET_ERROR", payload: null });

    if (!state.model.trim()) {
      dispatch({ type: "SET_ERROR", payload: "Model is required" });
      return;
    }

    const payload: StartRunPayload = {
      mode: state.mode,
      model: state.model.trim(),
      repetitions: state.repetitions,
      task_limit: state.taskLimit,
      source: state.source,
    };

    if (state.oaOverride) payload.oa_override = state.oaOverride;
    if (state.mode === "taguchi") {
      payload.pipeline_mode = state.pipelineMode;
      payload.quality_type = state.qualityType;
      payload.top_k = state.topK;
      payload.alpha = state.alpha;
    }

    startRun.mutate(payload, {
      onSuccess: (data) => {
        navigate(`/live?run_id=${data.run_id}`);
      },
      onError: (err) => {
        dispatch({ type: "SET_ERROR", payload: err.message || "Failed to start evaluation" });
        dispatch({ type: "SET_COOLDOWN", payload: true });
        clearTimeout(cooldownTimer.current);
        cooldownTimer.current = setTimeout(
          () => dispatch({ type: "SET_COOLDOWN", payload: false }),
          1500,
        );
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
          <FadeIn delay={1}>
            <Card>
              <CardContent>
                <ModeSelector
                  mode={state.mode}
                  onModeChange={(m) => dispatch({ type: "SET_MODE", payload: m })}
                />

                <div className="mt-sp-6">
                  <label
                    htmlFor="model"
                    className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
                  >
                    Model
                  </label>
                  <Input
                    id="model"
                    value={state.model}
                    onChange={(e) =>
                      dispatch({ type: "SET_MODEL", payload: e.target.value })
                    }
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
                    value={state.source}
                    onValueChange={(v) =>
                      dispatch({ type: "SET_SOURCE", payload: v })
                    }
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
                      value={state.repetitions}
                      onChange={(e) =>
                        dispatch({
                          type: "SET_REPETITIONS",
                          payload: parseInt(e.target.value) || 1,
                        })
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
                      value={state.taskLimit}
                      onChange={(e) =>
                        dispatch({
                          type: "SET_TASK_LIMIT",
                          payload: parseInt(e.target.value) || 0,
                        })
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
                      value={state.oaOverride}
                      onChange={(e) =>
                        dispatch({ type: "SET_OA_OVERRIDE", payload: e.target.value })
                      }
                      placeholder="e.g. L9_3_4"
                    />
                    <p className="mt-sp-1 text-caption text-brand-slate">
                      Force a specific orthogonal array (e.g. L9_3_4,
                      L27_3_13). Leave blank to auto-select based on factor
                      count.
                    </p>
                  </div>

                  {state.mode === "taguchi" && (
                    <TaguchiParams
                      pipelineMode={state.pipelineMode}
                      qualityType={state.qualityType}
                      topK={state.topK}
                      alpha={state.alpha}
                      dispatch={dispatch}
                    />
                  )}
                </div>
              </CardContent>
            </Card>
          </FadeIn>
        </div>

        <FadeIn delay={3}>
          {state.error && (
            <div className="mt-sp-4 rounded-card border border-red-300 bg-red-50 px-sp-4 py-sp-3 text-body-sm text-red-700">
              {state.error}
            </div>
          )}

          {activeCount > 0 && (
            <div className="mt-sp-4 rounded-card border border-brand-goldenrod/30 bg-brand-goldenrod/5 px-sp-4 py-sp-3 text-body-sm text-brand-charcoal">
              {activeCount} {activeCount === 1 ? "run" : "runs"} currently in progress.
            </div>
          )}

          <div className="mt-sp-8 flex justify-end">
            <Button type="submit" size="lg" disabled={isSubmitting || state.cooldown}>
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
