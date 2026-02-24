// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSSE } from "../hooks/useSSE";
import { useFilterParams } from "../hooks/useFilterParams";

// --- useSSE tests ---

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  readyState = 0;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, cb: (e: MessageEvent) => void) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(cb);
  }

  emit(event: string, data: unknown) {
    for (const cb of this.listeners[event] ?? []) {
      cb(new MessageEvent(event, { data: JSON.stringify(data) }));
    }
  }
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("useSSE", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("should connect to SSE endpoint when runId is provided", () => {
    renderHook(() => useSSE({ runId: "run-1" }), {
      wrapper: createWrapper(),
    });
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain("/api/runs/run-1/stream");
  });

  it("should not connect when runId is null", () => {
    renderHook(() => useSSE({ runId: null }), {
      wrapper: createWrapper(),
    });
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("should call onTrialComplete when trial_completed event fires", () => {
    const onTrialComplete = vi.fn();
    renderHook(
      () => useSSE({ runId: "run-1", onTrialComplete }),
      { wrapper: createWrapper() },
    );

    const source = MockEventSource.instances[0];
    source.emit("trial_completed", { task_id: "t1", score: 0.9 });

    expect(onTrialComplete).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: "t1", score: 0.9 }),
    );
  });

  it("should close EventSource on disconnect", () => {
    const { result } = renderHook(
      () => useSSE({ runId: "run-1" }),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.disconnect();
    });

    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  it("should clean up on unmount", () => {
    const { unmount } = renderHook(
      () => useSSE({ runId: "run-1" }),
      { wrapper: createWrapper() },
    );

    unmount();
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });
});

// --- useFilterParams tests ---

describe("useFilterParams", () => {
  it("should return empty filters by default", () => {
    const { result } = renderHook(() => useFilterParams(), {
      wrapper: createWrapper(),
    });
    const [filters] = result.current;
    expect(filters.search).toBeUndefined();
    expect(filters.free).toBeUndefined();
  });

  it("should read filters from URL search params", () => {
    const wrapper = ({ children }: { children: ReactNode }) => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return (
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={["/?search=gpt&free=true"]}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      );
    };

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;
    expect(filters.search).toBe("gpt");
    expect(filters.free).toBe(true);
  });

  it("should update filters via setFilters", () => {
    const { result } = renderHook(() => useFilterParams(), {
      wrapper: createWrapper(),
    });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ search: "claude" });
    });

    const [filters] = result.current;
    expect(filters.search).toBe("claude");
  });

  it("should remove filters with null/empty values", () => {
    const wrapper = ({ children }: { children: ReactNode }) => {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return (
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={["/?search=test"]}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      );
    };

    const { result } = renderHook(() => useFilterParams(), { wrapper });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ search: "" });
    });

    const [filters] = result.current;
    expect(filters.search).toBeUndefined();
  });
});
