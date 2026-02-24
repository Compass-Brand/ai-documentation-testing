import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelBreakdown } from "../../components/ModelBreakdown";

describe("ModelBreakdown", () => {
  it("should show empty message when no data", () => {
    render(<ModelBreakdown data={{}} />);
    expect(screen.getByText("No model data yet.")).toBeInTheDocument();
  });

  it("should render table headers", () => {
    render(
      <ModelBreakdown
        data={{
          "claude-3": { mean_score: 0.85, trial_count: 10, cost: 1.5 },
        }}
      />,
    );
    expect(screen.getByText("Model")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
    expect(screen.getByText("Trials")).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
  });

  it("should render model rows with formatted data", () => {
    render(
      <ModelBreakdown
        data={{
          "claude-3": { mean_score: 0.856, trial_count: 10, cost: 1.5 },
        }}
      />,
    );
    expect(screen.getByText("claude-3")).toBeInTheDocument();
    expect(screen.getByText("0.86")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("$1.50")).toBeInTheDocument();
  });

  it("should sort by trial count descending", () => {
    render(
      <ModelBreakdown
        data={{
          "model-a": { mean_score: 0.9, trial_count: 5, cost: 0.5 },
          "model-b": { mean_score: 0.8, trial_count: 20, cost: 2.0 },
          "model-c": { mean_score: 0.7, trial_count: 10, cost: 1.0 },
        }}
      />,
    );
    const rows = screen.getAllByRole("row");
    // First data row (index 1, after header) should be model-b (20 trials)
    expect(rows[1]).toHaveTextContent("model-b");
    expect(rows[2]).toHaveTextContent("model-c");
    expect(rows[3]).toHaveTextContent("model-a");
  });
});
