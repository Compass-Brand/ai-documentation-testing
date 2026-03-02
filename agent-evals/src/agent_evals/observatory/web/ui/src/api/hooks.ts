import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api, type ModelFilters, type StartRunPayload } from "./client";

const STALE_LONG = 30_000;
const STALE_MED = 10_000;
const STALE_SHORT = 5_000;
const GC_TIME = 300_000;

// --- Runs ---
export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: api.listRuns,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useTrials(runId: string | null, model?: string) {
  return useQuery({
    queryKey: ["trials", runId, model],
    queryFn: () => api.getTrials(runId!, model),
    enabled: !!runId,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useReport(runId: string | null) {
  return useQuery({
    queryKey: ["report", runId],
    queryFn: () => api.getReport(runId!),
    enabled: !!runId,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

// --- History ---
export function useCostTrend() {
  return useQuery({
    queryKey: ["cost-trend"],
    queryFn: api.costTrend,
    staleTime: STALE_SHORT,
    gcTime: GC_TIME,
  });
}

export function useModelDrift(model: string | null) {
  return useQuery({
    queryKey: ["model-drift", model],
    queryFn: () => api.modelDrift(model!),
    enabled: !!model,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useCompareRuns(ids: string[]) {
  return useQuery({
    queryKey: ["compare", ids],
    queryFn: () => api.compareRuns(ids),
    enabled: ids.length >= 2,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

// --- Models ---
export function useModels(filters: ModelFilters) {
  return useQuery({
    queryKey: ["models", filters],
    queryFn: () => api.listModels(filters),
    placeholderData: (prev) => prev,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}

export function useModelDetail(modelId: string | null) {
  return useQuery({
    queryKey: ["model", modelId],
    queryFn: () => api.getModel(modelId!),
    enabled: !!modelId,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}

export function useModelEndpoints(modelId: string | null) {
  return useQuery({
    queryKey: ["model-endpoints", modelId],
    queryFn: () => api.getModelEndpoints(modelId!),
    enabled: !!modelId,
    refetchInterval: 60_000,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}

// --- Groups ---
export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: api.listGroups,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      description,
    }: {
      name: string;
      description: string;
    }) => api.createGroup(name, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useAddGroupMembers() {
  return useMutation({
    mutationFn: ({
      groupId,
      modelIds,
    }: {
      groupId: string;
      modelIds: string[];
    }) => api.addGroupMembers(groupId, modelIds),
  });
}

// --- Sync ---
export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: api.syncStatus,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.triggerSync,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
  });
}

// --- Datasets ---
export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: api.listDatasets,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}

// --- Run Submission ---
export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartRunPayload) => api.startRun(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useActiveRuns() {
  return useQuery({
    queryKey: ["active-runs"],
    queryFn: api.getActiveRuns,
    refetchInterval: 5000,
    staleTime: STALE_SHORT,
    gcTime: GC_TIME,
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.cancelRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["active-runs"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

// --- Pipelines ---
export function usePipelines() {
  return useQuery({
    queryKey: ["pipelines"],
    queryFn: api.listPipelines,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function usePipeline(id: string | null) {
  return useQuery({
    queryKey: ["pipeline", id],
    queryFn: () => api.getPipeline(id!),
    enabled: !!id,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useRunAnalysis(runId: string | null) {
  return useQuery({
    queryKey: ["analysis", runId],
    queryFn: () => api.getRunAnalysis(runId!),
    enabled: !!runId,
    staleTime: STALE_MED,
    gcTime: GC_TIME,
  });
}

export function useApprovePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.approvePipeline(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
    },
  });
}
