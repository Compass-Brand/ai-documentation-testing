import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";

// Mock the api module
vi.mock("../../api/client", () => ({
  api: {
    listRuns: vi.fn().mockResolvedValue([]),
    getRun: vi.fn().mockResolvedValue({}),
    getTrials: vi.fn().mockResolvedValue([]),
    getReport: vi.fn().mockResolvedValue({}),
    costTrend: vi.fn().mockResolvedValue({}),
    modelDrift: vi.fn().mockResolvedValue({}),
    compareRuns: vi.fn().mockResolvedValue({}),
    listModels: vi.fn().mockResolvedValue({ models: [], total: 0 }),
    getModel: vi.fn().mockResolvedValue({}),
    getModelEndpoints: vi.fn().mockResolvedValue({ endpoints: [] }),
    listGroups: vi.fn().mockResolvedValue([]),
    createGroup: vi.fn().mockResolvedValue({}),
    addGroupMembers: vi.fn().mockResolvedValue({ warnings: [] }),
    syncStatus: vi.fn().mockResolvedValue({}),
    triggerSync: vi.fn().mockResolvedValue({}),
  },
}));

import { api } from "../../api/client";
import {
  useRuns,
  useRun,
  useTrials,
  useReport,
  useCostTrend,
  useModelDrift,
  useCompareRuns,
  useModels,
  useModelDetail,
  useModelEndpoints,
  useGroups,
  useCreateGroup,
  useAddGroupMembers,
  useSyncStatus,
  useTriggerSync,
} from "../../api/hooks";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe("Query hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useRuns uses queryKey ['runs'] and calls api.listRuns", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRuns(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listRuns).toHaveBeenCalledOnce();
  });

  it("useRun is disabled when runId is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRun(null), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it("useRun fetches when runId is provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useRun("run-1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getRun).toHaveBeenCalledWith("run-1");
  });

  it("useTrials is disabled when runId is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useTrials(null), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getTrials).not.toHaveBeenCalled();
  });

  it("useTrials passes model param to api.getTrials", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useTrials("run-1", "gpt-4o"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getTrials).toHaveBeenCalledWith("run-1", "gpt-4o");
  });

  it("useReport is disabled when runId is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useReport(null), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
  });

  it("useReport fetches when runId is provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useReport("run-1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getReport).toHaveBeenCalledWith("run-1");
  });

  it("useCostTrend uses queryKey ['cost-trend']", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useCostTrend(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.costTrend).toHaveBeenCalledOnce();
  });

  it("useModelDrift is disabled when model is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useModelDrift(null), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.modelDrift).not.toHaveBeenCalled();
  });

  it("useModelDrift fetches when model is provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModelDrift("gpt-4o"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.modelDrift).toHaveBeenCalledWith("gpt-4o");
  });

  it("useCompareRuns is disabled when fewer than 2 ids", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useCompareRuns(["run-1"]),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.compareRuns).not.toHaveBeenCalled();
  });

  it("useCompareRuns fetches when 2+ ids provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useCompareRuns(["run-1", "run-2"]),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.compareRuns).toHaveBeenCalledWith(["run-1", "run-2"]);
  });

  it("useModels passes filters to api.listModels", async () => {
    const filters = { search: "claude", free: true };
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModels(filters),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listModels).toHaveBeenCalledWith(filters);
  });

  it("useModelDetail is disabled when modelId is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModelDetail(null),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getModel).not.toHaveBeenCalled();
  });

  it("useModelDetail fetches when modelId is provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModelDetail("gpt-4o"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getModel).toHaveBeenCalledWith("gpt-4o");
  });

  it("useModelEndpoints is disabled when modelId is null", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModelEndpoints(null),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getModelEndpoints).not.toHaveBeenCalled();
  });

  it("useModelEndpoints fetches when modelId is provided", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useModelEndpoints("gpt-4o"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getModelEndpoints).toHaveBeenCalledWith("gpt-4o");
  });

  it("useGroups uses queryKey ['groups']", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useGroups(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listGroups).toHaveBeenCalledOnce();
  });

  it("useSyncStatus uses queryKey ['sync-status']", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useSyncStatus(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.syncStatus).toHaveBeenCalledOnce();
  });
});

describe("Mutation hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useCreateGroup calls api.createGroup with name and description", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useCreateGroup(), { wrapper });

    result.current.mutate({ name: "Test", description: "A group" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.createGroup).toHaveBeenCalledWith("Test", "A group");
  });

  it("useAddGroupMembers calls api.addGroupMembers", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useAddGroupMembers(), { wrapper });

    result.current.mutate({
      groupId: "g-1",
      modelIds: ["m-1", "m-2"],
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.addGroupMembers).toHaveBeenCalledWith("g-1", ["m-1", "m-2"]);
  });

  it("useTriggerSync calls api.triggerSync", async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useTriggerSync(), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.triggerSync).toHaveBeenCalledOnce();
  });
});
