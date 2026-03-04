import { useState } from "react";
import { Copy, Check } from "lucide-react";
import type { Model } from "../../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/Card";
import { StatusBadge } from "../../components/StatusBadge";
import { Tooltip } from "../../components/Tooltip";
import { Button } from "../../components/Button";
import { formatPrice } from "./models-utils";

function CopyModelIdButton({ modelId }: { modelId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const orId = modelId.startsWith("openrouter/")
      ? modelId
      : `openrouter/${modelId}`;
    navigator.clipboard.writeText(orId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Tooltip content={copied ? "Copied!" : "Copy OpenRouter model ID"}>
      <button
        className="relative h-3.5 w-3.5 text-brand-slate hover:text-brand-charcoal transition-colors duration-micro ml-sp-2"
        onClick={handleCopy}
        aria-label="Copy model ID"
      >
        <span
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-150 ${copied ? "opacity-0" : "opacity-100"}`}
        >
          <Copy className="h-3.5 w-3.5" />
        </span>
        <span
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-150 ${copied ? "opacity-100" : "opacity-0"}`}
        >
          <Check className="h-3.5 w-3.5 text-brand-sage" />
        </span>
      </button>
    </Tooltip>
  );
}

function ModelCard({
  model,
  onClick,
  maxContext,
}: {
  model: Model;
  onClick: () => void;
  maxContext: number;
}) {
  const provider = model.id.split("/")[0];
  const contextPct =
    maxContext > 0 ? (model.context_length / maxContext) * 100 : 0;

  return (
    <Card variant="interactive" onClick={onClick}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="truncate">{model.name}</CardTitle>
          <CopyModelIdButton modelId={model.id} />
        </div>
        <span className="text-caption text-brand-slate capitalize">
          {provider}
        </span>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-sp-2 mb-sp-3">
          <StatusBadge
            status={model.prompt_price === 0 ? "new" : "neutral"}
            label={
              model.prompt_price === 0
                ? "Free"
                : `${formatPrice(model.prompt_price)} in`
            }
          />
          {model.completion_price > 0 && (
            <StatusBadge
              status="neutral"
              label={`${formatPrice(model.completion_price)} out`}
            />
          )}
          <StatusBadge status="neutral" label={model.modality} />
        </div>
        <div className="mt-sp-3">
          <div className="flex justify-between text-caption text-brand-slate mb-sp-1">
            <span>Context</span>
            <span>{(model.context_length / 1000).toFixed(0)}k</span>
          </div>
          <div className="h-1.5 bg-brand-mist rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-goldenrod rounded-full transition-all duration-state"
              style={{ width: `${Math.max(contextPct, 2)}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface ModelsCardViewProps {
  models: Model[];
  maxContext: number;
  cardLimit: number;
  onCardClick: (id: string) => void;
  onLoadMore: () => void;
}

export function ModelsCardView({
  models,
  maxContext,
  cardLimit,
  onCardClick,
  onLoadMore,
}: ModelsCardViewProps) {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-sp-4">
        {models.slice(0, cardLimit).map((model) => (
          <ModelCard
            key={model.id}
            model={model}
            maxContext={maxContext}
            onClick={() => onCardClick(model.id)}
          />
        ))}
      </div>
      {models.length > cardLimit && (
        <div className="mt-sp-6 text-center">
          <Button variant="secondary" onClick={onLoadMore}>
            Show more ({models.length - cardLimit} remaining)
          </Button>
        </div>
      )}
    </>
  );
}
