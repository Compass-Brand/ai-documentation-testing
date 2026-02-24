import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VariantSummary } from "../../components/VariantSummary";

describe("VariantSummary", () => {
  it("should show empty message when no data", () => {
    render(<VariantSummary data={{}} />);
    expect(screen.getByText("No variant data yet.")).toBeInTheDocument();
  });

  it("should render table headers", () => {
    render(
      <VariantSummary
        data={{
          flat: { mean_score: 0.85, trial_count: 10 },
        }}
      />,
    );
    expect(screen.getByText("Variant")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
    expect(screen.getByText("Trials")).toBeInTheDocument();
  });

  it("should render variant rows with formatted data", () => {
    render(
      <VariantSummary
        data={{
          flat: { mean_score: 0.856, trial_count: 10 },
        }}
      />,
    );
    expect(screen.getByText("flat")).toBeInTheDocument();
    expect(screen.getByText("0.86")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("should sort by mean score descending", () => {
    render(
      <VariantSummary
        data={{
          "variant-a": { mean_score: 0.7, trial_count: 5 },
          "variant-b": { mean_score: 0.9, trial_count: 5 },
          "variant-c": { mean_score: 0.8, trial_count: 5 },
        }}
      />,
    );
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("variant-b");
    expect(rows[2]).toHaveTextContent("variant-c");
    expect(rows[3]).toHaveTextContent("variant-a");
  });
});
