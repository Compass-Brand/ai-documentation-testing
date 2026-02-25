// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "../../components/Tooltip";
import LiveMonitor from "../../pages/LiveMonitor";

// Mock useSSE
vi.mock("../../hooks/useSSE", () => ({
  useSSE: vi.fn(() => ({ disconnect: vi.fn() })),
}));

const mockUseLiveMonitorState = vi.fn();

vi.mock("../../hooks/useLiveMonitorState", () => ({
  useLiveMonitorState: (...args: unknown[]) => mockUseLiveMonitorState(...args),
}));

const mockUseActiveRuns = vi.fn();

vi.mock("../../api/hooks", () => ({
  useActiveRuns: (...args: unknown[]) => mockUseActiveRuns(...args),
}));

const defaultState = {
  selectedRunId: "run-1",
  setSelectedRunId: vi.fn(),
  recentTrials: [],
  alerts: [],
  progress: 30,
  trialsCompleted: 3,
  trialsTotal: 10,
  uniqueTasksSeen: 2,
  totalTasks: 355,
  trialsPerMin: 5.0,
  estimatedRemainingMinutes: 1.4,
  meanScore: 0.82,
  totalCost: 0.15,
  totalTokens: 5000,
  avgLatency: 1.2,
  errorCount: 0,
  byModel: { claude: { mean_score: 0.82, trial_count: 3, cost: 0.15 } },
  byVariant: { flat: { mean_score: 0.82, trial_count: 3 } },
  isConnected: true,
  lastUpdated: new Date(),
  isLoading: false,
  scores: [0.8, 0.85, 0.82],
};

function renderMonitor() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/live"]}>
        <TooltipProvider delayDuration={300}>
          <Routes>
            <Route path="/live" element={<LiveMonitor />} />
          </Routes>
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockUseLiveMonitorState.mockReturnValue(defaultState);
  mockUseActiveRuns.mockReturnValue({ data: { runs: [], count: 0 } });
});

describe("LiveMonitor", () => {
  it("should render the page heading", () => {
    renderMonitor();
    expect(screen.getByText("Live Monitor")).toBeInTheDocument();
  });

  it("should display progress information", () => {
    renderMonitor();
    expect(screen.getByText(/3\s*\/\s*10\s*trials/)).toBeInTheDocument();
  });

  it("should display task progress", () => {
    renderMonitor();
    expect(screen.getByText(/2\s*\/\s*355\s*tasks/)).toBeInTheDocument();
  });

  it("should display mean score stat", () => {
    renderMonitor();
    // Score appears in stat card and model/variant tables
    expect(screen.getAllByText("0.82").length).toBeGreaterThanOrEqual(1);
  });

  it("should display total cost stat", () => {
    renderMonitor();
    // Cost appears in stat card and model breakdown table
    expect(screen.getAllByText("$0.15").length).toBeGreaterThanOrEqual(1);
  });

  it("should display tokens stat", () => {
    renderMonitor();
    expect(screen.getByText("5K")).toBeInTheDocument();
  });

  it("should display latency stat", () => {
    renderMonitor();
    expect(screen.getByText("1.2s")).toBeInTheDocument();
  });

  it("should show Live indicator when connected", () => {
    renderMonitor();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("should show ETA", () => {
    renderMonitor();
    expect(screen.getByText(/~2m left/)).toBeInTheDocument();
  });

  it("should render model breakdown section", () => {
    renderMonitor();
    expect(screen.getByText("Per-Model Breakdown")).toBeInTheDocument();
    expect(screen.getByText("claude")).toBeInTheDocument();
  });

  it("should render variant summary section", () => {
    renderMonitor();
    expect(screen.getByText("Variant Summary")).toBeInTheDocument();
    expect(screen.getByText("flat")).toBeInTheDocument();
  });

  it("should render alerts section", () => {
    renderMonitor();
    expect(screen.getByText("Alerts")).toBeInTheDocument();
  });

  describe("empty state", () => {
    it("should show EmptyState when no selected run", () => {
      mockUseLiveMonitorState.mockReturnValue({
        ...defaultState,
        selectedRunId: null,
      });
      renderMonitor();
      expect(screen.getByText("No Active Runs")).toBeInTheDocument();
    });

    it("should show skeleton loading when isLoading", () => {
      mockUseLiveMonitorState.mockReturnValue({
        ...defaultState,
        isLoading: true,
      });
      const { container } = renderMonitor();
      expect(container.querySelector("[aria-hidden='true'].shimmer")).toBeInTheDocument();
    });
  });
});
