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

  // Helper to simulate events in tests
  emit(event: string, data: unknown) {
    const handlers = this.listeners[event] || [];
    for (const handler of handlers) {
      handler(new MessageEvent(event, { data: JSON.stringify(data) }));
    }
  }
}

// Mock fetch for polling
const mockFetchForPolling = vi.fn();

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

describe("useSSE", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("fetch", mockFetchForPolling);
    mockFetchForPolling.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "active" }),
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("should not connect when runId is null", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();

    renderHook(
      () => useSSE({ runId: null }),
      { wrapper },
    );

    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("should connect to /api/runs/{runId}/stream when runId is provided", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();

    renderHook(
      () => useSSE({ runId: "run-1" }),
      { wrapper },
    );

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe("/api/runs/run-1/stream");
  });

  it("should listen for trial_completed events", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onTrialComplete = vi.fn();

    renderHook(
      () => useSSE({ runId: "run-1", onTrialComplete }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    expect(source.listeners["trial_completed"]).toBeDefined();
    expect(source.listeners["trial_completed"].length).toBeGreaterThan(0);
  });

  it("should call onTrialComplete with parsed Trial data", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onTrialComplete = vi.fn();
    const trialData = { task_id: "t-1", score: 0.85 };

    renderHook(
      () => useSSE({ runId: "run-1", onTrialComplete }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    act(() => {
      source.emit("trial_completed", trialData);
    });

    expect(onTrialComplete).toHaveBeenCalledWith(trialData);
  });

  it("should close EventSource and clear poll on disconnect", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();

    const { result } = renderHook(
      () => useSSE({ runId: "run-1" }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    expect(source.closed).toBe(false);

    act(() => {
      result.current.disconnect();
    });

    expect(source.closed).toBe(true);
  });

  it("should close EventSource on unmount", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();

    const { unmount } = renderHook(
      () => useSSE({ runId: "run-1" }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    expect(source.closed).toBe(false);

    unmount();

    expect(source.closed).toBe(true);
  });

  it("should call onRunComplete when poll detects completed status", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onRunComplete = vi.fn();

    mockFetchForPolling.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "completed" }),
    });

    renderHook(
      () => useSSE({ runId: "run-1", onRunComplete }),
      { wrapper },
    );

    // Advance past the 5-second poll interval
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    // The poll should have triggered
    expect(mockFetchForPolling).toHaveBeenCalledWith("/api/runs/run-1");
    expect(onRunComplete).toHaveBeenCalled();
  });

  it("should listen for error events", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onError = vi.fn();

    renderHook(
      () => useSSE({ runId: "run-1", onError }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    expect(source.listeners["error"]).toBeDefined();
  });

  it("should listen for alert event types", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onAlert = vi.fn();

    renderHook(
      () => useSSE({ runId: "run-1", onAlert }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    expect(source.listeners["anomaly_alert"]).toBeDefined();
    expect(source.listeners["model_budget_exceeded"]).toBeDefined();
    expect(source.listeners["burn_rate_alert"]).toBeDefined();
  });

  it("does not crash when SSE delivers malformed JSON", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    renderHook(() => useSSE({ runId: "run1" }), { wrapper });

    const source = MockEventSource.instances[0];
    // Call the trial_completed listener directly with a bad-JSON MessageEvent
    expect(() => {
      act(() => {
        const handlers = source?.listeners["trial_completed"] ?? [];
        for (const handler of handlers) {
          handler(new MessageEvent("trial_completed", { data: "{not json!!" }));
        }
      });
    }).not.toThrow();
  });

  it("should call onAlert with parsed alert data", async () => {
    const { useSSE } = await import("../../hooks/useSSE");
    const wrapper = createWrapper();
    const onAlert = vi.fn();

    renderHook(
      () => useSSE({ runId: "run-1", onAlert }),
      { wrapper },
    );

    const source = MockEventSource.instances[0];
    const alertData = { model: "claude", cost: 0.08, average_cost: 0.02 };
    act(() => {
      source.emit("anomaly_alert", alertData);
    });

    expect(onAlert).toHaveBeenCalledWith({
      type: "anomaly_alert",
      data: alertData,
    });
  });
});
