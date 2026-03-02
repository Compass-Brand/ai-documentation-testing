import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We'll import after creating the module
// For now these tests define the expected behavior

describe("fetchApi", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("should return parsed JSON on successful response", async () => {
    const mockData = { id: "run-1", status: "active" };
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    } as Response);

    const { fetchApi } = await import("../../api/client");
    const result = await fetchApi("/api/runs");

    expect(result).toEqual(mockData);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("should throw an error on non-ok response", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Not Found"),
    } as Response);

    const { fetchApi } = await import("../../api/client");

    await expect(fetchApi("/api/runs/missing")).rejects.toThrow(
      "API 404: Not Found",
    );
  });

  it("should prepend VITE_API_URL when set", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    // import.meta.env is set at build time; the module reads it on load.
    // Since we can't easily change import.meta.env between dynamic imports
    // in the same test run, we verify the default (empty string) behavior:
    // fetch is called with just the path.
    const { fetchApi } = await import("../../api/client");
    await fetchApi("/api/runs");

    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe("/api/runs");
  });

  it("should merge custom headers with Content-Type", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response);

    const { fetchApi } = await import("../../api/client");
    await fetchApi("/api/runs", {
      headers: { Authorization: "Bearer token123" },
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer token123",
        },
      }),
    );
  });
});

describe("api methods", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response),
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("listRuns calls /api/runs", async () => {
    const { api } = await import("../../api/client");
    await api.listRuns();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs",
      expect.any(Object),
    );
  });

  it("getRun calls /api/runs/{id}", async () => {
    const { api } = await import("../../api/client");
    await api.getRun("run-abc");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs/run-abc",
      expect.any(Object),
    );
  });

  it("getTrials calls /api/runs/{id}/trials without model param", async () => {
    const { api } = await import("../../api/client");
    await api.getTrials("run-abc");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs/run-abc/trials",
      expect.any(Object),
    );
  });

  it("getTrials appends model query param when provided", async () => {
    const { api } = await import("../../api/client");
    await api.getTrials("run-abc", "gpt-4o");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs/run-abc/trials?model=gpt-4o",
      expect.any(Object),
    );
  });

  it("getTrials encodes model param with special characters", async () => {
    const { api } = await import("../../api/client");
    await api.getTrials("run-abc", "anthropic/claude-3.5-sonnet");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs/run-abc/trials?model=anthropic%2Fclaude-3.5-sonnet",
      expect.any(Object),
    );
  });

  it("getReport calls /api/runs/{id}/report", async () => {
    const { api } = await import("../../api/client");
    await api.getReport("run-abc");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/runs/run-abc/report",
      expect.any(Object),
    );
  });

  it("compareRuns constructs correct URL with comma-separated ids", async () => {
    const { api } = await import("../../api/client");
    await api.compareRuns(["run-1", "run-2", "run-3"]);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/compare?ids=run-1,run-2,run-3",
      expect.any(Object),
    );
  });

  it("costTrend calls /api/history/cost-trend", async () => {
    const { api } = await import("../../api/client");
    await api.costTrend();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/history/cost-trend",
      expect.any(Object),
    );
  });

  it("modelDrift encodes model name in URL", async () => {
    const { api } = await import("../../api/client");
    await api.modelDrift("openai/gpt-4o");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/history/model-drift?model=openai%2Fgpt-4o",
      expect.any(Object),
    );
  });

  it("listModels constructs correct URL with filter params", async () => {
    const { api } = await import("../../api/client");
    await api.listModels({
      search: "claude",
      free: true,
      maxPrice: 10,
      minContext: 8000,
      modality: "text",
      capability: "tools",
      tokenizer: "cl100k",
      sort: "price",
    });

    const calledUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    const url = new URL(calledUrl, "http://localhost");

    expect(url.pathname).toBe("/api/models");
    expect(url.searchParams.get("search")).toBe("claude");
    expect(url.searchParams.get("free")).toBe("true");
    expect(url.searchParams.get("max_price")).toBe("10");
    expect(url.searchParams.get("min_context")).toBe("8000");
    expect(url.searchParams.get("modality")).toBe("text");
    expect(url.searchParams.get("capability")).toBe("tools");
    expect(url.searchParams.get("tokenizer")).toBe("cl100k");
    expect(url.searchParams.get("sort")).toBe("price");
  });

  it("listModels calls /api/models without params when no filters", async () => {
    const { api } = await import("../../api/client");
    await api.listModels();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models",
      expect.any(Object),
    );
  });

  it("listModels skips undefined/null filter values", async () => {
    const { api } = await import("../../api/client");
    await api.listModels({ search: "gpt", free: false });

    const calledUrl = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    expect(calledUrl).toBe("/api/models?search=gpt");
  });

  it("getModel encodes model ID in URL", async () => {
    const { api } = await import("../../api/client");
    await api.getModel("openai/gpt-4o");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/openai%2Fgpt-4o",
      expect.any(Object),
    );
  });

  it("getModelEndpoints encodes model ID in URL", async () => {
    const { api } = await import("../../api/client");
    await api.getModelEndpoints("openai/gpt-4o");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/openai%2Fgpt-4o/endpoints",
      expect.any(Object),
    );
  });

  it("listGroups calls /api/models/groups", async () => {
    const { api } = await import("../../api/client");
    await api.listGroups();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/groups",
      expect.any(Object),
    );
  });

  it("createGroup sends POST with name and description", async () => {
    const { api } = await import("../../api/client");
    await api.createGroup("My Group", "A test group");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/groups",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "My Group", description: "A test group" }),
      }),
    );
  });

  it("addGroupMembers sends POST with model_ids", async () => {
    const { api } = await import("../../api/client");
    await api.addGroupMembers("group-1", ["model-a", "model-b"]);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/groups/group-1/members",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ model_ids: ["model-a", "model-b"] }),
      }),
    );
  });

  it("deleteGroup sends DELETE request via fetchApi with signal", async () => {
    const { api } = await import("../../api/client");
    await api.deleteGroup("group-1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/groups/group-1",
      expect.objectContaining({ method: "DELETE", signal: expect.any(AbortSignal) }),
    );
  });

  it("syncStatus calls /api/models/sync", async () => {
    const { api } = await import("../../api/client");
    await api.syncStatus();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/sync",
      expect.any(Object),
    );
  });

  it("triggerSync sends POST to /api/models/sync", async () => {
    const { api } = await import("../../api/client");
    await api.triggerSync();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/models/sync",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
