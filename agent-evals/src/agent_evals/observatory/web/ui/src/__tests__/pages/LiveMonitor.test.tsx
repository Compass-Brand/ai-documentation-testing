// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LiveMonitor from "../../pages/LiveMonitor";

// Mock useSSE
vi.mock("../../hooks/useSSE", () => ({
  useSSE: vi.fn(() => ({ disconnect: vi.fn() })),
}));

// Mock useRun to return sample data
vi.mock("../../api/hooks", () => ({
  useRun: vi.fn(() => ({
    data: {
      run: {
        run_id: "run-1",
        run_type: "taguchi",
        status: "active",
        config: {},
        created_at: "2026-02-23T00:00:00Z",
        finished_at: null,
      },
      total_trials: 10,
      completed_trials: 3,
      total_cost: 0.15,
      total_tokens: 5000,
      mean_score: 0.82,
      by_variant: { flat: { mean_score: 0.82, trial_count: 3 } },
    },
    isLoading: false,
    error: null,
  })),
  useTrials: vi.fn(() => ({
    data: [
      {
        task_id: "t1",
        task_type: "retrieval",
        variant_name: "flat",
        repetition: 1,
        score: 0.85,
        cost: 0.05,
        latency_seconds: 1.2,
        error: null,
        prompt_tokens: 100,
        completion_tokens: 50,
        total_tokens: 150,
        cached: false,
        source: "claude",
        metrics: {},
      },
    ],
    isLoading: false,
  })),
}));

function renderAtRoute(runId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/live/${runId}`]}>
        <Routes>
          <Route path="/live/:runId" element={<LiveMonitor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LiveMonitor", () => {
  it("should render the page heading", () => {
    renderAtRoute("run-1");
    expect(screen.getByText("Live Monitor")).toBeInTheDocument();
  });

  it("should display progress information", () => {
    renderAtRoute("run-1");
    // Should show "3 / 10 trials" progress text
    expect(screen.getByText(/3\s*\/\s*10\s*trials/)).toBeInTheDocument();
  });

  it("should display mean score stat", () => {
    renderAtRoute("run-1");
    expect(screen.getByText(/0\.82/)).toBeInTheDocument();
  });

  it("should display total cost stat", () => {
    renderAtRoute("run-1");
    expect(screen.getByText(/0\.15/)).toBeInTheDocument();
  });

  it("should render trial feed entries", () => {
    renderAtRoute("run-1");
    // Should show trial task ID or score
    expect(screen.getByText(/t1/i)).toBeInTheDocument();
  });
});
