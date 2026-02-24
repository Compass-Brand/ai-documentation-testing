import { useState, useEffect, useCallback } from "react";
import {
  Cpu,
  LayoutGrid,
  LayoutList,
  Play,
  Save,
  Copy,
  Check,
  X,
} from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  useModels,
  useModelDetail,
  useModelEndpoints,
  useCreateGroup,
  useSyncStatus,
  useTriggerSync,
} from "../api/hooks";
import { useFilterParams } from "../hooks/useFilterParams";
import type { Model, ProviderEndpoint } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { SlideOutPanel } from "../components/SlideOutPanel";
import {
  FilterSection,
  FilterCheckbox,
  FilterRange,
} from "../components/FilterPanel";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { StatusBadge } from "../components/StatusBadge";
import { StatusDot } from "../components/StatusDot";
import { FadeIn } from "../components/FadeIn";
import { Skeleton } from "../components/Skeleton";
import { Tooltip } from "../components/Tooltip";
import { TabBar } from "../components/TabBar";
import { cn } from "../lib/utils";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

type ViewMode = "table" | "cards";
type PanelTab = "overview" | "providers" | "history";

function latencyColor(ms: number): string {
  if (ms < 100) return "text-brand-sage";
  if (ms < 500) return "text-brand-amber";
  return "text-brand-clay";
}

function formatPrice(price: number): string {
  if (price === 0) return "Free";
  const perMillion = price * 1_000_000;
  if (perMillion < 0.01) return "<$0.01/M";
  return `$${perMillion.toFixed(2)}/M`;
}

function formatDeployed(timestamp: number): string {
  if (!timestamp) return "\u2014";
  return new Date(timestamp * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function CopyModelIdButton({ modelId }: { modelId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const orId = modelId.startsWith("openrouter/") ? modelId : `openrouter/${modelId}`;
    navigator.clipboard.writeText(orId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Tooltip content="Copy OpenRouter model ID">
      <button
        className="text-brand-slate hover:text-brand-charcoal transition-colors duration-micro ml-sp-2"
        onClick={handleCopy}
        aria-label="Copy model ID"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-brand-sage" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
    </Tooltip>
  );
}

function ModelNameCell({
  model,
  onNameClick,
}: {
  model: Model;
  onNameClick: (model: Model) => void;
}) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onNameClick(model);
  };

  return (
    <span className="inline-flex items-center">
      <button
        className="text-brand-goldenrod cursor-pointer hover:underline font-medium"
        onClick={handleClick}
      >
        {model.name}
      </button>
      <CopyModelIdButton modelId={model.id} />
    </span>
  );
}

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
        <span className={cn("text-right font-medium", latencyColor(endpoint.latency_ms))}>
          {endpoint.latency_ms}ms
        </span>
        <span>Uptime</span>
        <span className="text-right">{endpoint.uptime_pct.toFixed(1)}%</span>
        <span>Quantization</span>
        <span className="text-right">{endpoint.quantization || "None"}</span>
      </div>
    </div>
  );
}

function ModelCard({
  model,
  onClick,
}: {
  model: Model;
  onClick: () => void;
}) {
  return (
    <Card
      className="cursor-pointer"
      onClick={onClick}
    >
      <CardHeader>
        <CardTitle>{model.name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-sp-2 mb-sp-3">
          <StatusBadge
            status={model.prompt_price === 0 ? "new" : "neutral"}
            label={model.prompt_price === 0 ? "Free" : formatPrice(model.prompt_price)}
          />
          <StatusBadge status="neutral" label={model.modality} />
        </div>
        <p className="text-caption text-brand-slate">
          {(model.context_length / 1000).toFixed(0)}k context
        </p>
      </CardContent>
    </Card>
  );
}

export function Models() {
  useDocumentTitle("Models");
  const [filters, setFilters] = useFilterParams();
  const { data: modelsData, isLoading } = useModels(filters);
  const [selectedModelIds, setSelectedModelIds] = useState<Set<string>>(new Set());
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [panelTab, setPanelTab] = useState<PanelTab>("overview");

  const { data: modelDetail } = useModelDetail(selectedModelId);
  const { data: endpointsData } = useModelEndpoints(selectedModelId);
  useSyncStatus();
  useTriggerSync();
  const createGroup = useCreateGroup();

  const models = modelsData?.models ?? [];
  const total = modelsData?.total ?? 0;
  const endpoints = endpointsData?.endpoints ?? [];

  const selectedModels = models.filter((m) => selectedModelIds.has(m.id));

  const clearSelection = useCallback(() => {
    setSelectedModelIds(new Set());
  }, []);

  // Escape key clears selection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        clearSelection();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection]);

  const handleRowClick = (model: Model) => {
    setSelectedModelIds((prev) => {
      const next = new Set(prev);
      if (next.has(model.id)) {
        next.delete(model.id);
      } else {
        next.add(model.id);
      }
      return next;
    });
  };

  const handleNameClick = (model: Model) => {
    setSelectedModelId(model.id);
    setPanelTab("overview");
  };

  const columns: ColumnDef<Model>[] = [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <ModelNameCell model={row.original} onNameClick={handleNameClick} />
      ),
    },
    {
      accessorKey: "prompt_price",
      header: () => (
        <Tooltip content="Cost per million prompt (input) tokens">
          <span className="cursor-help">Prompt $/M</span>
        </Tooltip>
      ),
      cell: ({ getValue }) => formatPrice(getValue<number>()),
    },
    {
      accessorKey: "completion_price",
      header: () => (
        <Tooltip content="Cost per million completion (output) tokens">
          <span className="cursor-help">Completion $/M</span>
        </Tooltip>
      ),
      cell: ({ getValue }) => formatPrice(getValue<number>()),
    },
    {
      accessorKey: "context_length",
      header: "Context",
      cell: ({ getValue }) => `${(getValue<number>() / 1000).toFixed(0)}k`,
    },
    { accessorKey: "modality", header: "Modality" },
    { accessorKey: "tokenizer", header: "Tokenizer" },
    {
      accessorKey: "created",
      header: "Deployed",
      cell: ({ getValue }) => formatDeployed(getValue<number>()),
    },
  ];

  if (isLoading) {
    return (
      <div className="px-sp-6 py-sp-8">
        <div className="space-y-sp-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="text" className="h-10" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="px-sp-6 py-sp-8 max-w-full 2xl:max-w-[1400px] mx-auto">
      <FadeIn>
        <h1 className="text-h2 text-brand-charcoal inline-flex items-center gap-sp-3 mb-sp-8">
          <Cpu className="h-8 w-8 text-brand-goldenrod" />
          Models
        </h1>
      </FadeIn>

      <div className="flex gap-sp-6">
        {/* Left sidebar -- 264px */}
        <aside className="hidden lg:block w-[264px] shrink-0">
          <FadeIn delay={1}>
            <Input
              placeholder="Search models..."
              value={filters.search ?? ""}
              onChange={(e) => setFilters({ search: e.target.value })}
            />

            <div className="mt-sp-6">
              <FilterSection label="Pricing">
                <FilterCheckbox
                  label="Free models only"
                  checked={filters.free ?? false}
                  onCheckedChange={(checked) =>
                    setFilters({ free: checked || undefined })
                  }
                />
                <FilterRange
                  label="Max price per 1M tokens"
                  min={0}
                  max={100}
                  value={[0, filters.maxPrice ?? 100]}
                  onChange={([, max]) => setFilters({ maxPrice: max })}
                  format={(n) => `$${n}`}
                />
              </FilterSection>

              <FilterSection label="Context Length">
                <FilterRange
                  label="Min context length"
                  min={0}
                  max={1000}
                  value={[filters.minContext ? filters.minContext / 1000 : 0, 1000]}
                  onChange={([min]) =>
                    setFilters({ minContext: min > 0 ? min * 1000 : undefined })
                  }
                  format={(n) => `${n}k`}
                />
              </FilterSection>

              <FilterSection label="Modality">
                {["text->text", "text+image->text", "text->image"].map((m) => (
                  <FilterCheckbox
                    key={m}
                    label={m}
                    checked={filters.modality === m}
                    onCheckedChange={(checked) =>
                      setFilters({ modality: checked ? m : undefined })
                    }
                  />
                ))}
              </FilterSection>

              <p className="text-caption text-brand-slate mt-sp-4">
                {total} models found
              </p>
            </div>
          </FadeIn>
        </aside>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <FadeIn delay={2}>
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-sp-6">
              <div className="flex items-center gap-sp-3">
                {selectedModels.length > 0 && (
                  <>
                    <span className="text-body-sm text-brand-slate">
                      {selectedModels.length} selected
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={clearSelection}
                    >
                      <X className="h-4 w-4 mr-sp-1" />
                      Clear
                    </Button>
                  </>
                )}
                <Button
                  variant="primary"
                  size="sm"
                  disabled={selectedModels.length === 0}
                >
                  <Play className="h-4 w-4 mr-sp-2" />
                  Run Selected
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={selectedModels.length === 0}
                  onClick={() => {
                    if (selectedModels.length > 0) {
                      createGroup.mutate({
                        name: `Group ${Date.now()}`,
                        description: `${selectedModels.length} models`,
                      });
                    }
                  }}
                >
                  <Save className="h-4 w-4 mr-sp-2" />
                  Save as Group
                </Button>
              </div>
              <div className="flex items-center gap-sp-1">
                <button
                  aria-label="Table view"
                  className={cn(
                    "rounded-card p-sp-2 transition-colors duration-micro",
                    viewMode === "table"
                      ? "bg-brand-goldenrod/10 text-brand-goldenrod"
                      : "text-brand-slate hover:text-brand-charcoal",
                  )}
                  onClick={() => setViewMode("table")}
                >
                  <LayoutList className="h-5 w-5" />
                </button>
                <button
                  aria-label="Card view"
                  className={cn(
                    "rounded-card p-sp-2 transition-colors duration-micro",
                    viewMode === "cards"
                      ? "bg-brand-goldenrod/10 text-brand-goldenrod"
                      : "text-brand-slate hover:text-brand-charcoal",
                  )}
                  onClick={() => setViewMode("cards")}
                >
                  <LayoutGrid className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Table / Card grid */}
            {viewMode === "table" ? (
              <DataTable
                columns={columns}
                data={models}
                selectedRowIds={selectedModelIds}
                getRowId={(model) => model.id}
                onRowClick={handleRowClick}
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-sp-4">
                {models.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    onClick={() => {
                      setSelectedModelId(model.id);
                      setPanelTab("overview");
                    }}
                  />
                ))}
              </div>
            )}
          </FadeIn>
        </div>
      </div>

      {/* SlideOutPanel -- model detail */}
      <SlideOutPanel
        open={selectedModelId !== null}
        onClose={() => setSelectedModelId(null)}
        title={modelDetail?.name ?? "Model Details"}
        width="lg"
      >
        {/* Tabs */}
        <div className="mb-sp-6">
          <TabBar
            tabs={[
              { key: "overview", label: "Overview" },
              { key: "providers", label: "Providers" },
              { key: "history", label: "History" },
            ]}
            activeKey={panelTab}
            onTabChange={(key) => setPanelTab(key as PanelTab)}
          />
        </div>

        {/* Tab content */}
        {panelTab === "overview" && modelDetail && (
          <div className="space-y-sp-6">
            {/* Pricing */}
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

            {/* Info grid */}
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
            </div>

            {/* Capabilities */}
            {modelDetail.supported_params.length > 0 && (
              <div>
                <p className="text-body-sm font-medium text-brand-charcoal mb-sp-3">
                  Capabilities
                </p>
                <div className="flex flex-wrap gap-sp-2">
                  {modelDetail.supported_params.map((param) => (
                    <StatusBadge
                      key={param}
                      status="neutral"
                      label={param}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* API ID */}
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
                  onClick={() => navigator.clipboard.writeText(
                    modelDetail.id.startsWith("openrouter/") ? modelDetail.id : `openrouter/${modelDetail.id}`
                  )}
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
              <span className="text-brand-slate">First Seen</span>
              <span className="text-brand-charcoal">
                {new Date(modelDetail.first_seen * 1000).toLocaleDateString()}
              </span>
            </div>
            <div className="flex justify-between text-body-sm">
              <span className="text-brand-slate">Last Seen</span>
              <span className="text-brand-charcoal">
                {new Date(modelDetail.last_seen * 1000).toLocaleDateString()}
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
    </div>
  );
}
