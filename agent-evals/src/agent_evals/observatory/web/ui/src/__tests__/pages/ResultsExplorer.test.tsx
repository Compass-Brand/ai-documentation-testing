import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

// Mock chart.js to avoid canvas issues in jsdom
vi.mock("react-chartjs-2", () => ({
  Bar: (props: Record<string, unknown>) =>
    createElement("canvas", { "data-testid": "bar-chart", ...props }),
  Radar: (props: Record<string, unknown>) =>
    createElement("canvas", { "data-testid": "radar-chart", ...props }),
}));

vi.mock("chart.js", () => ({
  Chart: { register: vi.fn() },
  CategoryScale: class {},
  LinearScale: class {},
  BarElement: class {},
  RadialLinearScale: class {},
  PointElement: class {},
  LineElement: class {},
  Filler: class {},
  Tooltip: class {},
  Legend: class {},
}));

// Mock the hooks
const mockUseRuns = vi.fn();
const mockUseRun = vi.fn();
const mockUseTrials = vi.fn();

vi.mock("../../api/hooks", () => ({
  useRuns: () => mockUseRuns(),
  useRun: (id: string | null) => mockUseRun(id),
  useTrials: (id: string | null) => mockUseTrials(id),
}));

const sampleRuns = [
  {
    run_id: "run-1",
    run_type: "taguchi",
    status: "completed" as const,
    config: {},
    created_at: "2026-02-23T10:00:00Z",
    finished_at: "2026-02-23T11:00:00Z",
  },
  {
    run_id: "run-2",
    run_type: "full",
    status: "active" as const,
    config: {},
    created_at: "2026-02-23T12:00:00Z",
    finished_at: null,
  },
];

const sampleRunSummary = {
  run: sampleRuns[0],
  total_trials: 100,
  completed_trials: 95,
  total_cost: 12.5,
  total_tokens: 500000,
  mean_score: 0.78,
  by_variant: {
    "variant-a": { mean_score: 0.82, trial_count: 50 },
    "variant-b": { mean_score: 0.74, trial_count: 45 },
  },
  by_model: {
    "gpt-4o": { mean_score: 0.85, trial_count: 50, cost: 8.0 },
    "claude-3.5-sonnet": { mean_score: 0.71, trial_count: 45, cost: 4.5 },
  },
};

const sampleRunSummaryNoModel = {
  ...sampleRunSummary,
  by_model: undefined,
};

function createWrapper(initialEntries: string[] = ["/results/run-1"]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries },
        createElement(
          Routes,
          null,
          createElement(Route, {
            path: "/results/:runId?",
            element: children,
          }),
        ),
      ),
    );
  };
}

describe("ResultsExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRuns.mockReturnValue({ data: sampleRuns, isLoading: false });
    mockUseRun.mockReturnValue({
      data: sampleRunSummary,
      isLoading: false,
    });
    mockUseTrials.mockReturnValue({ data: [], isLoading: false });
  });

  it("should render page heading with BarChart3 icon", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(
      screen.getByRole("heading", { name: /results explorer/i }),
    ).toBeInTheDocument();
  });

  it("should render a run selector dropdown", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    const selector = screen.getByRole("combobox", { name: /select run/i });
    expect(selector).toBeInTheDocument();
  });

  it("should display 3 summary stat cards", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.getByText("100")).toBeInTheDocument(); // total trials
    expect(screen.getByText("0.78")).toBeInTheDocument(); // mean score
    expect(screen.getByText("$12.50")).toBeInTheDocument(); // total cost
  });

  it("should render a horizontal bar chart of variant scores", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("should render a radar chart when by_model is present", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.getByTestId("radar-chart")).toBeInTheDocument();
  });

  it("should NOT render radar chart when by_model is absent", async () => {
    mockUseRun.mockReturnValue({
      data: sampleRunSummaryNoModel,
      isLoading: false,
    });

    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.queryByTestId("radar-chart")).not.toBeInTheDocument();
  });

  it("should render a variant breakdown table", async () => {
    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.getByText("variant-a")).toBeInTheDocument();
    expect(screen.getByText("variant-b")).toBeInTheDocument();
  });

  it("should show loading state when data is loading", async () => {
    mockUseRun.mockReturnValue({ data: undefined, isLoading: true });

    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper();

    render(createElement(ResultsExplorer), { wrapper });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("should show prompt when no run is selected", async () => {
    mockUseRun.mockReturnValue({ data: undefined, isLoading: false });

    const { ResultsExplorer } = await import("../../pages/ResultsExplorer");
    const wrapper = createWrapper(["/results"]);

    render(createElement(ResultsExplorer), { wrapper });

    expect(
      screen.getByText(/select a run to view results/i),
    ).toBeInTheDocument();
  });
});
