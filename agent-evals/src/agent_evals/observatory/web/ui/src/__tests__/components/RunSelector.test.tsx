import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RunSelector } from "../../components/RunSelector";

const mockUseActiveRuns = vi.fn();

vi.mock("../../api/hooks", () => ({
  useActiveRuns: (...args: unknown[]) => mockUseActiveRuns(...args),
}));

function renderSelector(
  selectedRunId: string | null = null,
  onSelectRun = vi.fn(),
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunSelector selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
    </QueryClientProvider>,
  );
}

describe("RunSelector", () => {
  beforeEach(() => {
    mockUseActiveRuns.mockReturnValue({ data: { runs: [], count: 0 } });
  });

  it("should return null when no active runs", () => {
    const { container } = renderSelector();
    expect(container.innerHTML).toBe("");
  });

  it("should show simple badge for single run", () => {
    mockUseActiveRuns.mockReturnValue({
      data: {
        runs: [{ run_id: "abc12345-full-id", mode: "taguchi", models: [], started_at: "" }],
        count: 1,
      },
    });
    renderSelector();
    expect(screen.getByText("taguchi")).toBeInTheDocument();
    expect(screen.getByText("abc12345")).toBeInTheDocument();
  });

  it("should show tab bar for multiple runs", () => {
    mockUseActiveRuns.mockReturnValue({
      data: {
        runs: [
          { run_id: "run-1111-full", mode: "taguchi", models: [], started_at: "" },
          { run_id: "run-2222-full", mode: "full", models: [], started_at: "" },
        ],
        count: 2,
      },
    });
    renderSelector("run-1111-full");
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });

  it("should highlight selected run tab", () => {
    mockUseActiveRuns.mockReturnValue({
      data: {
        runs: [
          { run_id: "run-1111-full", mode: "taguchi", models: [], started_at: "" },
          { run_id: "run-2222-full", mode: "full", models: [], started_at: "" },
        ],
        count: 2,
      },
    });
    renderSelector("run-1111-full");
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveAttribute("aria-selected", "false");
  });

  it("should call onSelectRun when tab is clicked", () => {
    mockUseActiveRuns.mockReturnValue({
      data: {
        runs: [
          { run_id: "run-1111-full", mode: "taguchi", models: [], started_at: "" },
          { run_id: "run-2222-full", mode: "full", models: [], started_at: "" },
        ],
        count: 2,
      },
    });
    const onSelectRun = vi.fn();
    renderSelector("run-1111-full", onSelectRun);
    fireEvent.click(screen.getAllByRole("tab")[1]);
    expect(onSelectRun).toHaveBeenCalledWith("run-2222-full");
  });
});
