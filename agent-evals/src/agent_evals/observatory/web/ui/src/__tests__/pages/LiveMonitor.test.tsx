// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LiveMonitor from "../../pages/LiveMonitor";

// Mock useSSE
vi.mock("../../hooks/useSSE", () => ({
  useSSE: vi.fn(() => ({ disconnect: vi.fn() })),
}));

const mockUseRuns = vi.fn();
const mockUseRun = vi.fn();
const mockUseTrials = vi.fn();

vi.mock("../../api/hooks", () => ({
  useRuns: (...args: unknown[]) => mockUseRuns(...args),
  useRun: (...args: unknown[]) => mockUseRun(...args),
  useTrials: (...args: unknown[]) => mockUseTrials(...args),
}));

const sampleRunSummary = {
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
};

const sampleTrials = [
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
];

beforeEach(() => {
  mockUseRuns.mockReturnValue({ data: [], isLoading: false });
  mockUseRun.mockReturnValue({ data: sampleRunSummary, isLoading: false, error: null });
  mockUseTrials.mockReturnValue({ data: sampleTrials, isLoading: false });
});

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

function renderNoRunId() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/live"]}>
        <Routes>
          <Route path="/live" element={<LiveMonitor />} />
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

  describe("auto-detection (no runId in URL)", () => {
    it("should auto-select the most recent active run", () => {
      mockUseRuns.mockReturnValue({
        data: [
          {
            run_id: "old-run",
            status: "completed",
            created_at: "2026-02-20T00:00:00Z",
            finished_at: "2026-02-20T01:00:00Z",
          },
          {
            run_id: "active-old",
            status: "active",
            created_at: "2026-02-21T00:00:00Z",
            finished_at: null,
          },
          {
            run_id: "active-latest",
            status: "active",
            created_at: "2026-02-23T00:00:00Z",
            finished_at: null,
          },
        ],
        isLoading: false,
      });

      renderNoRunId();

      // useRun should have been called with the latest active run
      expect(mockUseRun).toHaveBeenCalledWith("active-latest");
    });

    it("should show no-active-runs message when none are active", () => {
      mockUseRuns.mockReturnValue({
        data: [
          {
            run_id: "old-run",
            status: "completed",
            created_at: "2026-02-20T00:00:00Z",
            finished_at: "2026-02-20T01:00:00Z",
          },
        ],
        isLoading: false,
      });
      mockUseRun.mockReturnValue({ data: undefined, isLoading: false, error: null });

      renderNoRunId();

      expect(screen.getByText(/no active runs/i)).toBeInTheDocument();
    });

    it("should show loading while fetching runs list", () => {
      mockUseRuns.mockReturnValue({ data: undefined, isLoading: true });
      mockUseRun.mockReturnValue({ data: undefined, isLoading: false, error: null });

      renderNoRunId();

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });
});
