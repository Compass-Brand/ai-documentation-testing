// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const mockUsePipeline = vi.fn();
const mockUsePipelines = vi.fn();

vi.mock("../../api/hooks", () => ({
  usePipeline: (id: string | null) => mockUsePipeline(id),
  usePipelines: () => mockUsePipelines(),
}));

const samplePipeline = {
  pipeline_id: "pipe-1",
  runs: [
    { run_id: "r1", run_type: "taguchi", status: "completed", config: { phase: "screening" }, created_at: "2026-02-23T10:00:00Z", finished_at: "2026-02-23T10:30:00Z" },
    { run_id: "r2", run_type: "taguchi", status: "completed", config: { phase: "confirmation" }, created_at: "2026-02-23T11:00:00Z", finished_at: "2026-02-23T11:30:00Z" },
    { run_id: "r3", run_type: "taguchi", status: "active", config: { phase: "refinement" }, created_at: "2026-02-23T12:00:00Z", finished_at: null },
  ],
};

const samplePipelines = [
  { pipeline_id: "pipe-1", run_count: 3, latest_status: "active" },
  { pipeline_id: "pipe-2", run_count: 1, latest_status: "completed" },
];

function createWrapper(initialEntries: string[] = ["/pipeline/pipe-1"]) {
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
            path: "/pipeline/:pipelineId?",
            element: children,
          }),
        ),
      ),
    );
  };
}

describe("PipelineView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePipeline.mockReturnValue({
      data: samplePipeline,
      isLoading: false,
    });
    mockUsePipelines.mockReturnValue({
      data: samplePipelines,
      isLoading: false,
    });
  });

  it("should render Pipeline View heading", async () => {
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper() });
    expect(
      screen.getByRole("heading", { name: /pipeline view/i }),
    ).toBeInTheDocument();
  });

  it("should render three phase cards", async () => {
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper() });
    expect(screen.getByText(/Screening/i)).toBeInTheDocument();
    expect(screen.getByText(/Confirmation/i)).toBeInTheDocument();
    expect(screen.getByText(/Refinement/i)).toBeInTheDocument();
  });

  it("should show pipeline ID in the details section", async () => {
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper() });
    // The pipeline ID should appear in a styled label, not just in the selector
    const pipelineLabel = screen.getByText("pipe-1", {
      selector: ".font-medium",
    });
    expect(pipelineLabel).toBeInTheDocument();
  });

  it("should show phase status indicators", async () => {
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper() });
    const completedBadges = screen.getAllByText(/completed/i);
    expect(completedBadges.length).toBeGreaterThanOrEqual(2);
  });

  it("should show loading state", async () => {
    mockUsePipeline.mockReturnValue({ data: undefined, isLoading: true });
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper() });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("should show prompt when no pipeline is selected", async () => {
    mockUsePipeline.mockReturnValue({ data: undefined, isLoading: false });
    const { PipelineView } = await import("../../pages/PipelineView");
    render(createElement(PipelineView), { wrapper: createWrapper(["/pipeline"]) });
    expect(
      screen.getByText(/select a pipeline to view/i),
    ).toBeInTheDocument();
  });
});
