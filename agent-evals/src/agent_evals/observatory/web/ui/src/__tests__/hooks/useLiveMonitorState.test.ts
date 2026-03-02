import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(handler);
  }

  close() {
    this.closed = true;
  }

  emit(event: string, data: unknown) {
    const handlers = this.listeners[event] || [];
    for (const handler of handlers) {
      handler(new MessageEvent(event, { data: JSON.stringify(data) }));
    }
  }
}

const mockUseActiveRuns = vi.fn();
const mockUseRun = vi.fn();
const mockUseTrials = vi.fn();

vi.mock("../../api/hooks", () => ({
  useActiveRuns: (...args: unknown[]) => mockUseActiveRuns(...args),
  useRun: (...args: unknown[]) => mockUseRun(...args),
  useTrials: (...args: unknown[]) => mockUseTrials(...args),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

describe("useLiveMonitorState", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "active" }),
    }));
    vi.useFakeTimers();

    mockUseActiveRuns.mockReturnValue({
      data: {
        runs: [{ run_id: "run-1", mode: "taguchi", models: [], started_at: "" }],
        count: 1,
      },
    });
    mockUseRun.mockReturnValue({
      data: {
        run: { run_id: "run-1", status: "active", created_at: "2026-02-24T00:00:00Z" },
        total_trials: 100,
        completed_trials: 50,
        total_cost: 2.5,
        total_tokens: 50000,
        mean_score: 0.82,
        by_variant: { flat: { mean_score: 0.82, trial_count: 50 } },
        by_model: { claude: { mean_score: 0.82, trial_count: 50, cost: 2.5 } },
        unique_tasks: 25,
        avg_latency: 1.5,
      },
      isLoading: false,
    });
    mockUseTrials.mockReturnValue({ data: [], isLoading: false });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("should auto-select first active run", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    expect(result.current.selectedRunId).toBe("run-1");
  });

  it("should return null selectedRunId when no active runs", async () => {
    mockUseActiveRuns.mockReturnValue({ data: { runs: [], count: 0 } });
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    expect(result.current.selectedRunId).toBeNull();
  });

  it("should compute progress from summary", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    expect(result.current.progress).toBe(50);
    expect(result.current.trialsCompleted).toBe(50);
    expect(result.current.trialsTotal).toBe(100);
  });

  it("should expose summary stats", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    expect(result.current.meanScore).toBe(0.82);
    expect(result.current.totalCost).toBe(2.5);
    expect(result.current.totalTokens).toBe(50000);
    expect(result.current.avgLatency).toBe(1.5);
    expect(result.current.uniqueTasksSeen).toBe(25);
  });

  it("should expose byModel and byVariant", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    expect(result.current.byModel).toHaveProperty("claude");
    expect(result.current.byVariant).toHaveProperty("flat");
  });

  it("should allow manual run selection", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });

    act(() => {
      result.current.setSelectedRunId("run-2");
    });

    expect(result.current.selectedRunId).toBe("run-2");
  });

  it("scores array stays bounded after many trials", async () => {
    const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
    const wrapper = createWrapper();
    const { result } = renderHook(() => useLiveMonitorState(), { wrapper });
    act(() => {
      for (let i = 0; i < 1500; i++) {
        MockEventSource.instances[0]?.emit("trial_completed", { score: 0.5, task_id: `t${i}` });
      }
    });
    expect(result.current.scores.length).toBeLessThanOrEqual(1000);
  });
});
