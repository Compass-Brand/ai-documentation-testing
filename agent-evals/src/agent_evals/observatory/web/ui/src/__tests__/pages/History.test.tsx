import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { History } from "../../pages/History";

// Mock the API hooks
vi.mock("../../api/hooks", () => ({
  useRuns: vi.fn(),
  useCostTrend: vi.fn(),
  useCompareRuns: vi.fn(),
}));

import { useRuns, useCostTrend, useCompareRuns } from "../../api/hooks";

const mockRuns = [
  {
    run_id: "run-1",
    run_type: "taguchi",
    status: "completed" as const,
    config: {},
    created_at: "2026-02-20T10:00:00Z",
    finished_at: "2026-02-20T11:00:00Z",
  },
  {
    run_id: "run-2",
    run_type: "full",
    status: "completed" as const,
    config: {},
    created_at: "2026-02-21T10:00:00Z",
    finished_at: "2026-02-21T12:00:00Z",
  },
  {
    run_id: "run-3",
    run_type: "taguchi",
    status: "active" as const,
    config: {},
    created_at: "2026-02-22T10:00:00Z",
    finished_at: null,
  },
];

const mockCostTrend = {
  labels: ["run-1", "run-2", "run-3"],
  costs: [1.5, 2.3, 0.8],
};

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

beforeEach(() => {
  vi.mocked(useRuns).mockReturnValue({
    data: mockRuns,
    isLoading: false,
    error: null,
  } as ReturnType<typeof useRuns>);

  vi.mocked(useCostTrend).mockReturnValue({
    data: mockCostTrend,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useCostTrend>);

  vi.mocked(useCompareRuns).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  } as ReturnType<typeof useCompareRuns>);
});

describe("History page", () => {
  it("should render page heading with History icon", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("History")).toBeInTheDocument();
  });

  it("should render cost trend chart section", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("Cost Trend")).toBeInTheDocument();
  });

  it("should render accessible chart wrapper for cost trend", () => {
    render(<History />, { wrapper: createWrapper() });
    const chart = document.querySelector('[role="img"]');
    expect(chart).toBeInTheDocument();
  });

  it("should render runs table with run data", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("run-1")).toBeInTheDocument();
    expect(screen.getByText("run-2")).toBeInTheDocument();
    expect(screen.getByText("run-3")).toBeInTheDocument();
  });

  it("should show run type column", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("Type")).toBeInTheDocument();
  });

  it("should show run status column", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("should show loading state", () => {
    vi.mocked(useRuns).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof useRuns>);
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("should show compare section heading", () => {
    render(<History />, { wrapper: createWrapper() });
    expect(screen.getByText("Compare Runs")).toBeInTheDocument();
  });
});
