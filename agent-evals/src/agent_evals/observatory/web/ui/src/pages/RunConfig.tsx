import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { FadeIn } from "../components/FadeIn";
import { cn } from "../lib/utils";

type RunMode = "taguchi" | "full";

export default function RunConfig() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<RunMode>("taguchi");
  const [model, setModel] = useState("");
  const [repetitions, setRepetitions] = useState(3);
  const [taskLimit, setTaskLimit] = useState(0);
  const [oaOverride, setOaOverride] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Navigate to live monitor (run creation is CLI-driven per spec)
    const params = new URLSearchParams({
      mode,
      model,
      repetitions: String(repetitions),
    });
    if (taskLimit > 0) params.set("task_limit", String(taskLimit));
    if (oaOverride) params.set("oa_override", oaOverride);
    navigate(`/live?${params.toString()}`);
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
                            ? "Fractional factorial design"
                            : "All combinations"}
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
                  </div>
                </div>
              </CardContent>
            </Card>
          </FadeIn>
        </div>

        <FadeIn delay={3}>
          <div className="mt-sp-8 flex justify-end">
            <Button type="submit" size="lg">
              <Play className="mr-sp-2 h-5 w-5" />
              Start Evaluation
            </Button>
          </div>
        </FadeIn>
      </form>
    </div>
  );
}
