import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "../../components/Tooltip";
import type { ReactNode } from "react";

// Mock chart.js
vi.mock("react-chartjs-2", () => ({
  Bar: (props: Record<string, unknown>) =>
    createElement("canvas", { "data-testid": "main-effects-chart", ...props }),
}));

vi.mock("chart.js", () => ({
  Chart: { register: vi.fn() },
  CategoryScale: class {},
  LinearScale: class {},
  BarElement: class {},
  Tooltip: class {},
  Legend: class {},
}));

const mockUseRunAnalysis = vi.fn();

vi.mock("../../api/hooks", () => ({
  useRunAnalysis: (id: string | null) => mockUseRunAnalysis(id),
}));

const sampleAnalysis = {
  main_effects: {
    structure: { flat: 10.0, nested: 12.3 },
    granularity: { fine: 11.0, coarse: 10.5 },
  },
  anova: {
    structure: {
      ss: 15.2,
      df: 1,
      ms: 15.2,
      f_ratio: 8.9,
      p_value: 0.001,
      eta_squared: 0.12,
      omega_squared: 0.089,
    },
    granularity: {
      ss: 2.1,
      df: 1,
      ms: 2.1,
      f_ratio: 1.2,
      p_value: 0.35,
      eta_squared: 0.02,
      omega_squared: 0.003,
    },
  },
  optimal: { structure: "nested", granularity: "fine" },
  significant_factors: ["structure"],
  quality_type: "larger_is_better",
};

function createWrapper(initialEntries: string[] = ["/analysis/run-1"]) {
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
          TooltipProvider,
          { delayDuration: 300 },
          createElement(
            Routes,
            null,
            createElement(Route, {
              path: "/analysis/:runId",
              element: children,
            }),
          ),
        ),
      ),
    );
  };
}

describe("FactorAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRunAnalysis.mockReturnValue({
      data: sampleAnalysis,
      isLoading: false,
    });
  });

  it("should render Main Effects heading", async () => {
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    expect(screen.getByText(/Main Effects/i)).toBeInTheDocument();
  });

  it("should render ANOVA table", async () => {
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    expect(screen.getByText(/ANOVA/i)).toBeInTheDocument();
  });

  it("should mark significant factors", async () => {
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    const badges = screen.getAllByText("Significant");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it("should show optimal prediction", async () => {
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    expect(screen.getByText(/Optimal/i)).toBeInTheDocument();
    expect(screen.getByText(/nested/)).toBeInTheDocument();
  });

  it("should render main effects chart", async () => {
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    expect(screen.getByTestId("main-effects-chart")).toBeInTheDocument();
  });

  it("should show loading state", async () => {
    mockUseRunAnalysis.mockReturnValue({ data: undefined, isLoading: true });
    const { FactorAnalysis } = await import("../../pages/FactorAnalysis");
    const { container } = render(createElement(FactorAnalysis), { wrapper: createWrapper() });
    expect(container.querySelector("[aria-hidden='true'].shimmer")).toBeInTheDocument();
  });
});
