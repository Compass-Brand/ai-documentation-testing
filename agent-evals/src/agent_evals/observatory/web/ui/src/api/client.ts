const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export async function fetchApi<T>(
  path: string,
  opts?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...opts?.headers },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

// --- Type Definitions ---

export interface Run {
  run_id: string;
  run_type: string;
  status: "active" | "completed" | "failed";
  config: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface Trial {
  task_id: string;
  task_type: string;
  variant_name: string;
  repetition: number;
  score: number;
  metrics: Record<string, number>;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  latency_seconds: number;
  cached: boolean;
  error: string | null;
  source: string;
  model?: string;
  oa_row_id?: number;
}

export interface RunSummary {
  run: Run;
  total_trials: number;
  completed_trials: number;
  total_cost: number;
  total_tokens: number;
  mean_score: number;
  by_variant: Record<
    string,
    { mean_score: number; trial_count: number }
  >;
  by_model?: Record<
    string,
    { mean_score: number; trial_count: number; cost: number }
  >;
}

export interface ModelFilters {
  search?: string;
  free?: boolean;
  maxPrice?: number;
  minContext?: number;
  modality?: string;
  capability?: string;
  tokenizer?: string;
  sort?: string;
}

export interface Model {
  id: string;
  name: string;
  context_length: number;
  prompt_price: number;
  completion_price: number;
  modality: string;
  tokenizer: string;
  first_seen: number;
  last_seen: number;
  removed_at: number | null;
}

export interface ModelDetail extends Model {
  created: number;
  supported_params: string[];
}

export interface ProviderEndpoint {
  provider: string;
  latency_ms: number;
  uptime_pct: number;
  pricing_diff: number;
  quantization: string;
  supported_params: string[];
  zero_downtime_routing: boolean;
}

export interface ModelGroup {
  id: string;
  name: string;
  description: string;
}

export interface SyncStatus {
  total_models: number;
  last_sync: number;
  models_added: number;
  models_removed: number;
  models_updated: number;
}

export interface SyncResult {
  added: number;
  removed: number;
  updated: number;
}

// --- Pipeline Types ---

export interface PipelineListItem {
  pipeline_id: string;
  run_count: number;
  latest_status: string;
}

export interface Pipeline {
  pipeline_id: string;
  runs: Run[];
}

export interface PhaseResults {
  main_effects: Record<string, Record<string, number>>;
  anova: Record<
    string,
    {
      ss: number;
      df: number;
      ms: number;
      f_ratio: number;
      p_value: number;
      eta_squared: number;
      omega_squared: number;
    }
  >;
  optimal: Record<string, string>;
  significant_factors: string[];
  quality_type: string;
  confirmation?: {
    within_interval: boolean;
    sigma_deviation: number;
    observed_sn: number;
    predicted_sn: number;
    prediction_interval: [number, number];
  };
}

// --- API Methods ---

export const api = {
  // Runs
  listRuns: () => fetchApi<Run[]>("/api/runs"),
  getRun: (id: string) => fetchApi<RunSummary>(`/api/runs/${id}`),
  getTrials: (id: string, model?: string) => {
    const params = model ? `?model=${encodeURIComponent(model)}` : "";
    return fetchApi<Trial[]>(`/api/runs/${id}/trials${params}`);
  },
  getReport: (id: string) =>
    fetchApi<Record<string, unknown>>(`/api/runs/${id}/report`),

  // Comparison and history
  compareRuns: (ids: string[]) =>
    fetchApi<RunSummary[]>(
      `/api/compare?ids=${ids.join(",")}`,
    ),
  costTrend: () =>
    fetchApi<Record<string, unknown>>("/api/history/cost-trend"),
  modelDrift: (model: string) =>
    fetchApi<Record<string, unknown>>(
      `/api/history/model-drift?model=${encodeURIComponent(model)}`,
    ),

  // Models
  listModels: (filters?: ModelFilters) => {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.free) params.set("free", "true");
    if (filters?.maxPrice != null)
      params.set("max_price", String(filters.maxPrice));
    if (filters?.minContext != null)
      params.set("min_context", String(filters.minContext));
    if (filters?.modality) params.set("modality", filters.modality);
    if (filters?.capability) params.set("capability", filters.capability);
    if (filters?.tokenizer) params.set("tokenizer", filters.tokenizer);
    if (filters?.sort) params.set("sort", filters.sort);
    const qs = params.toString();
    return fetchApi<{ models: Model[]; total: number }>(
      `/api/models${qs ? `?${qs}` : ""}`,
    );
  },
  getModel: (id: string) =>
    fetchApi<ModelDetail>(`/api/models/${encodeURIComponent(id)}`),
  getModelEndpoints: (id: string) =>
    fetchApi<{ endpoints: ProviderEndpoint[] }>(
      `/api/models/${encodeURIComponent(id)}/endpoints`,
    ),

  // Groups
  listGroups: () => fetchApi<ModelGroup[]>("/api/models/groups"),
  createGroup: (name: string, description: string) =>
    fetchApi<ModelGroup>("/api/models/groups", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  addGroupMembers: (groupId: string, modelIds: string[]) =>
    fetchApi<{ warnings: string[] }>(
      `/api/models/groups/${groupId}/members`,
      {
        method: "POST",
        body: JSON.stringify({ model_ids: modelIds }),
      },
    ),
  deleteGroup: (groupId: string) =>
    fetch(`${BASE_URL}/api/models/groups/${groupId}`, {
      method: "DELETE",
    }),

  // Sync
  syncStatus: () => fetchApi<SyncStatus>("/api/models/sync"),
  triggerSync: () =>
    fetchApi<SyncResult>("/api/models/sync", { method: "POST" }),

  // Pipelines
  listPipelines: () => fetchApi<PipelineListItem[]>("/api/pipelines"),
  getPipeline: (id: string) =>
    fetchApi<Pipeline>(`/api/pipelines/${id}`),
  getRunAnalysis: (runId: string) =>
    fetchApi<PhaseResults>(`/api/runs/${runId}/analysis`),
  approvePipeline: (id: string) =>
    fetchApi<{ status: string }>(`/api/pipelines/${id}/approve`, {
      method: "POST",
    }),
};
