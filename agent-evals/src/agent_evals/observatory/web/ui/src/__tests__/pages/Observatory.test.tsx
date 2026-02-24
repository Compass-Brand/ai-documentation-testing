import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

// Mock chart.js to avoid canvas issues in jsdom
vi.mock("react-chartjs-2", () => ({
  Line: (props: Record<string, unknown>) =>
    createElement("canvas", { "data-testid": "line-chart", ...props }),
  Doughnut: (props: Record<string, unknown>) =>
    createElement("canvas", { "data-testid": "doughnut-chart", ...props }),
}));

vi.mock("chart.js", () => ({
  Chart: { register: vi.fn() },
  CategoryScale: class {},
  LinearScale: class {},
  PointElement: class {},
  LineElement: class {},
  ArcElement: class {},
  Filler: class {},
  Tooltip: class {},
  Legend: class {},
}));

// Mock the hooks
const mockUseRuns = vi.fn();
const mockUseRun = vi.fn();
const mockUseCostTrend = vi.fn();

vi.mock("../../api/hooks", () => ({
  useRuns: () => mockUseRuns(),
  useRun: (id: string | null) => mockUseRun(id),
  useCostTrend: () => mockUseCostTrend(),
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
  },
  by_model: {
    "gpt-4o": { mean_score: 0.85, trial_count: 50, cost: 8.0 },
    "claude-3.5-sonnet": { mean_score: 0.71, trial_count: 45, cost: 4.5 },
  },
};

const sampleCostTrend = {
  runs: [
    { run_id: "run-1", cost: 12.5, created_at: "2026-02-23T10:00:00Z" },
  ],
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(MemoryRouter, null, children),
    );
  };
}

describe("Observatory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRuns.mockReturnValue({ data: sampleRuns, isLoading: false });
    mockUseRun.mockReturnValue({
      data: sampleRunSummary,
      isLoading: false,
    });
    mockUseCostTrend.mockReturnValue({
      data: sampleCostTrend,
      isLoading: false,
    });
  });

  it("should render page heading with Eye icon", async () => {
    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(
      screen.getByRole("heading", { name: /observatory/i }),
    ).toBeInTheDocument();
  });

  it("should display 3 cost stat cards", async () => {
    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(screen.getByText("$12.50")).toBeInTheDocument(); // total spend
    expect(screen.getByText("500,000")).toBeInTheDocument(); // total tokens
    expect(screen.getByText("$0.13")).toBeInTheDocument(); // cost per trial (12.5/100)
  });

  it("should render a cost burn line chart", async () => {
    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(screen.getByTestId("line-chart")).toBeInTheDocument();
  });

  it("should render a doughnut chart when by_model is present", async () => {
    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(screen.getByTestId("doughnut-chart")).toBeInTheDocument();
  });

  it("should NOT render doughnut chart when by_model is absent", async () => {
    mockUseRun.mockReturnValue({
      data: { ...sampleRunSummary, by_model: undefined },
      isLoading: false,
    });

    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(screen.queryByTestId("doughnut-chart")).not.toBeInTheDocument();
  });

  it("should show loading state", async () => {
    mockUseRuns.mockReturnValue({ data: undefined, isLoading: true });
    mockUseRun.mockReturnValue({ data: undefined, isLoading: true });
    mockUseCostTrend.mockReturnValue({ data: undefined, isLoading: true });

    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("should display run selector", async () => {
    const { Observatory } = await import("../../pages/Observatory");
    const wrapper = createWrapper();

    render(createElement(Observatory), { wrapper });

    const selector = screen.getByRole("combobox", { name: /select run/i });
    expect(selector).toBeInTheDocument();
  });
});
