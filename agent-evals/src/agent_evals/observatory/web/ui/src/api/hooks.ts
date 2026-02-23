import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api, type ModelFilters, type Pipeline, type PhaseResults } from "./client";

// --- Runs ---
export function useRuns() {
  return useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
  });
}

export function useTrials(runId: string | null, model?: string) {
  return useQuery({
    queryKey: ["trials", runId, model],
    queryFn: () => api.getTrials(runId!, model),
    enabled: !!runId,
  });
}

export function useReport(runId: string | null) {
  return useQuery({
    queryKey: ["report", runId],
    queryFn: () => api.getReport(runId!),
    enabled: !!runId,
  });
}

// --- History ---
export function useCostTrend() {
  return useQuery({
    queryKey: ["cost-trend"],
    queryFn: api.costTrend,
  });
}

export function useModelDrift(model: string | null) {
  return useQuery({
    queryKey: ["model-drift", model],
    queryFn: () => api.modelDrift(model!),
    enabled: !!model,
  });
}

export function useCompareRuns(ids: string[]) {
  return useQuery({
    queryKey: ["compare", ids],
    queryFn: () => api.compareRuns(ids),
    enabled: ids.length >= 2,
  });
}

// --- Models ---
export function useModels(filters: ModelFilters) {
  return useQuery({
    queryKey: ["models", filters],
    queryFn: () => api.listModels(filters),
    placeholderData: (prev) => prev,
  });
}

export function useModelDetail(modelId: string | null) {
  return useQuery({
    queryKey: ["model", modelId],
    queryFn: () => api.getModel(modelId!),
    enabled: !!modelId,
  });
}

export function useModelEndpoints(modelId: string | null) {
  return useQuery({
    queryKey: ["model-endpoints", modelId],
    queryFn: () => api.getModelEndpoints(modelId!),
    enabled: !!modelId,
    refetchInterval: 60_000,
  });
}

// --- Groups ---
export function useGroups() {
  return useQuery({ queryKey: ["groups"], queryFn: api.listGroups });
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

// --- Pipelines ---
export function usePipelines() {
  return useQuery({
    queryKey: ["pipelines"],
    queryFn: api.listPipelines,
  });
}

export function usePipeline(id: string | null) {
  return useQuery({
    queryKey: ["pipeline", id],
    queryFn: () => api.getPipeline(id!),
    enabled: !!id,
  });
}

export function useRunAnalysis(runId: string | null) {
  return useQuery({
    queryKey: ["analysis", runId],
    queryFn: () => api.getRunAnalysis(runId!),
    enabled: !!runId,
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
