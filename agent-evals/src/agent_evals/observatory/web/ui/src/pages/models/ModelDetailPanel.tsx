import { Copy } from "lucide-react";
import type { ModelDetail, ProviderEndpoint } from "../../api/client";
import { SlideOutPanel } from "../../components/SlideOutPanel";
import { StatusBadge } from "../../components/StatusBadge";
import { StatusDot } from "../../components/StatusDot";
import { TabBar } from "../../components/TabBar";
import { cn } from "../../lib/utils";
import type { PanelTab } from "./useModelsReducer";
import { formatPrice, formatDeployed, latencyColor } from "./models-utils";

function ProviderCard({ endpoint }: { endpoint: ProviderEndpoint }) {
  return (
    <div className="rounded-card border border-brand-mist p-sp-4 mb-sp-3">
      <div className="flex items-center justify-between mb-sp-2">
        <span className="text-body-sm font-medium text-brand-charcoal">
          {endpoint.provider}
        </span>
        <StatusDot
          status={endpoint.uptime_pct > 99 ? "success" : "warning"}
        />
      </div>
      <div className="grid grid-cols-2 gap-sp-2 text-caption text-brand-slate">
        <span>Latency</span>
        <span
          className={cn(
            "text-right font-medium",
            latencyColor(endpoint.latency_ms),
          )}
        >
          {endpoint.latency_ms}ms
        </span>
        <span>Uptime</span>
        <span className="text-right">
          {endpoint.uptime_pct.toFixed(1)}%
        </span>
        <span>Quantization</span>
        <span className="text-right">
          {endpoint.quantization || "None"}
        </span>
      </div>
    </div>
  );
}

interface ModelDetailPanelProps {
  selectedModelId: string | null;
  modelDetail: ModelDetail | undefined;
  endpoints: ProviderEndpoint[];
  panelTab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  onClose: () => void;
}

export function ModelDetailPanel({
  selectedModelId,
  modelDetail,
  endpoints,
  panelTab,
  onTabChange,
  onClose,
}: ModelDetailPanelProps) {
  if (selectedModelId === null) return null;

  return (
    <SlideOutPanel
      open={selectedModelId !== null}
      onClose={onClose}
      title={modelDetail?.name ?? "Model Details"}
      width="lg"
    >
      <div className="mb-sp-6">
        <TabBar
          tabs={[
            { key: "overview", label: "Overview" },
            {
              key: "providers",
              label: `Providers${endpoints.length > 0 ? ` (${endpoints.length})` : ""}`,
            },
            { key: "history", label: "History" },
          ]}
          activeKey={panelTab}
          onTabChange={(key) => onTabChange(key as PanelTab)}
        />
      </div>

      {panelTab === "overview" && modelDetail && (
        <div className="space-y-sp-6">
          <div className="grid grid-cols-2 gap-sp-4">
            <div className="rounded-card border border-brand-mist p-sp-4">
              <p className="text-caption text-brand-slate mb-sp-1">
                Prompt Price
              </p>
              <p className="text-h5 text-brand-charcoal">
                {formatPrice(modelDetail.prompt_price)}
              </p>
            </div>
            <div className="rounded-card border border-brand-mist p-sp-4">
              <p className="text-caption text-brand-slate mb-sp-1">
                Completion Price
              </p>
              <p className="text-h5 text-brand-charcoal">
                {formatPrice(modelDetail.completion_price)}
              </p>
            </div>
          </div>
          <p className="text-caption text-brand-slate text-center mt-sp-2">
            ~$
            {(
              (modelDetail.prompt_price + modelDetail.completion_price) *
              1_000_000
            ).toFixed(2)}
            /M tokens (in + out)
          </p>

          <div className="space-y-sp-3">
            <div className="flex justify-between text-body-sm">
              <span className="text-brand-slate">Context Length</span>
              <span className="text-brand-charcoal font-medium">
                {(modelDetail.context_length / 1000).toFixed(0)}k tokens
              </span>
            </div>
            <div className="flex justify-between text-body-sm">
              <span className="text-brand-slate">Modality</span>
              <span className="text-brand-charcoal font-medium">
                {modelDetail.modality}
              </span>
            </div>
            <div className="flex justify-between text-body-sm">
              <span className="text-brand-slate">Tokenizer</span>
              <span className="text-brand-charcoal font-medium">
                {modelDetail.tokenizer}
              </span>
            </div>
            <div className="flex justify-between text-body-sm">
              <span className="text-brand-slate">Status</span>
              <StatusBadge
                status={modelDetail.removed_at ? "error" : "success"}
                label={modelDetail.removed_at ? "Deprecated" : "Active"}
              />
            </div>
            {modelDetail.created > 0 && (
              <div className="flex justify-between text-body-sm">
                <span className="text-brand-slate">Created</span>
                <span className="text-brand-charcoal font-medium">
                  {formatDeployed(modelDetail.created)}
                </span>
              </div>
            )}
          </div>

          {modelDetail.supported_params.length > 0 && (
            <div>
              <p className="text-body-sm font-medium text-brand-charcoal mb-sp-3">
                Capabilities
              </p>
              <div className="flex flex-wrap gap-sp-2">
                {modelDetail.supported_params.map((param) => (
                  <StatusBadge key={param} status="neutral" label={param} />
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-body-sm font-medium text-brand-charcoal mb-sp-2">
              API ID
            </p>
            <div className="flex items-center gap-sp-2 rounded-card bg-brand-cream p-sp-3">
              <code className="text-data text-brand-charcoal flex-1 truncate">
                {modelDetail.id}
              </code>
              <button
                className="text-brand-slate hover:text-brand-charcoal transition-colors duration-micro"
                onClick={() =>
                  navigator.clipboard.writeText(
                    modelDetail.id.startsWith("openrouter/")
                      ? modelDetail.id
                      : `openrouter/${modelDetail.id}`,
                  )
                }
                aria-label="Copy API ID"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {panelTab === "providers" && (
        <div>
          {endpoints.length === 0 ? (
            <p className="text-body-sm text-brand-slate">
              No provider data available.
            </p>
          ) : (
            endpoints.map((ep) => (
              <ProviderCard key={ep.provider} endpoint={ep} />
            ))
          )}
        </div>
      )}

      {panelTab === "history" && modelDetail && (
        <div className="space-y-sp-4">
          <div className="flex justify-between text-body-sm">
            <span className="text-brand-slate">Created</span>
            <span className="text-brand-charcoal">
              {formatDeployed(modelDetail.created)}
            </span>
          </div>
          <div className="flex justify-between text-body-sm">
            <span className="text-brand-slate">First Seen</span>
            <span className="text-brand-charcoal">
              {new Date(modelDetail.first_seen).toLocaleDateString()}
            </span>
          </div>
          <div className="flex justify-between text-body-sm">
            <span className="text-brand-slate">Last Seen</span>
            <span className="text-brand-charcoal">
              {new Date(modelDetail.last_seen).toLocaleDateString()}
            </span>
          </div>
          <div className="flex justify-between text-body-sm">
            <span className="text-brand-slate">Deprecation</span>
            <StatusBadge
              status={modelDetail.removed_at ? "error" : "success"}
              label={modelDetail.removed_at ? "Deprecated" : "Active"}
            />
          </div>
        </div>
      )}

      {!modelDetail && selectedModelId && (
        <p className="text-body-sm text-brand-slate">Loading details...</p>
      )}
    </SlideOutPanel>
  );
}
