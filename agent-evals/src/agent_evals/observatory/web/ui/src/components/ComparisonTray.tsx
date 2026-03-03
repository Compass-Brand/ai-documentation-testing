import { motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "../lib/utils";

interface ComparisonTrayModel {
  id: string;
  name: string;
  prompt_price: number;
  completion_price: number;
  context_length: number;
  modality: string;
  supported_params?: string[];
}

export interface ComparisonTrayProps {
  models: ComparisonTrayModel[];
  onClose: () => void;
}

function formatPrice(price: number): string {
  if (price === 0) return "Free";
  const perMillion = price * 1_000_000;
  if (perMillion < 0.01) return "<$0.01/M";
  return `$${perMillion.toFixed(2)}/M`;
}

function formatContext(contextLength: number): string {
  return `${(contextLength / 1000).toFixed(0)}k`;
}

/**
 * Collect all unique capabilities across models, then identify
 * which are unique to a single model (for diff highlighting).
 */
function getCapabilityDiff(models: ComparisonTrayModel[]) {
  const capCount = new Map<string, number>();
  for (const model of models) {
    const params = model.supported_params ?? [];
    for (const param of params) {
      capCount.set(param, (capCount.get(param) ?? 0) + 1);
    }
  }
  const uniqueCaps = new Set<string>();
  for (const [cap, count] of capCount) {
    if (count < models.length) {
      uniqueCaps.add(cap);
    }
  }
  return uniqueCaps;
}

function StatRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between text-body-sm py-sp-1">
      <span className="text-brand-slate">{label}</span>
      <span className="text-brand-charcoal font-medium">{children}</span>
    </div>
  );
}

function ModelColumn({
  model,
  uniqueCaps,
}: {
  model: ComparisonTrayModel;
  uniqueCaps: Set<string>;
}) {
  const params = model.supported_params ?? [];

  return (
    <div className="min-w-0">
      <p className="text-body font-semibold text-brand-charcoal truncate mb-sp-3">
        {model.name}
      </p>
      <div className="space-y-sp-1">
        <StatRow label="Prompt">{formatPrice(model.prompt_price)}</StatRow>
        <StatRow label="Completion">{formatPrice(model.completion_price)}</StatRow>
        <StatRow label="Context">{formatContext(model.context_length)}</StatRow>
        <StatRow label="Modality">{model.modality}</StatRow>
      </div>
      {params.length > 0 && (
        <div className="mt-sp-3">
          <p className="text-caption text-brand-slate mb-sp-2">Capabilities</p>
          <div className="flex flex-wrap gap-sp-1">
            {params.map((param) => (
              <span
                key={param}
                className={cn(
                  "inline-block text-caption px-sp-2 py-0.5 rounded-full border",
                  uniqueCaps.has(param)
                    ? "bg-brand-goldenrod/15 border-brand-goldenrod/30 text-brand-charcoal font-medium"
                    : "bg-brand-cream border-brand-mist text-brand-slate",
                )}
              >
                {param}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ComparisonTray({ models, onClose }: ComparisonTrayProps) {
  const uniqueCaps = getCapabilityDiff(models);
  const gridCols = models.length === 2 ? "grid-cols-2" : "grid-cols-3";

  return (
    <motion.div
      initial={{ y: "100%" }}
      animate={{ y: 0 }}
      exit={{ y: "100%" }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-sm border-t border-brand-mist shadow-[0_-4px_24px_rgba(0,0,0,0.1)]"
    >
      <div className="max-w-[1800px] mx-auto px-sp-6 py-sp-4 max-h-[300px] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-sp-4">
          <h2 className="text-h5 text-brand-charcoal">Compare Models</h2>
          <button
            onClick={onClose}
            className="rounded-card p-sp-1 text-brand-slate hover:text-brand-charcoal hover:bg-brand-mist/50 transition-colors duration-micro"
            aria-label="Close comparison"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Side-by-side columns */}
        <div className={cn("grid gap-sp-6", gridCols)}>
          {models.map((model) => (
            <ModelColumn
              key={model.id}
              model={model}
              uniqueCaps={uniqueCaps}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
