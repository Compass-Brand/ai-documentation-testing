import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AccessibleChart } from "../../components/AccessibleChart";

describe("AccessibleChart", () => {
  it("should render with role=img", () => {
    render(
      <AccessibleChart label="Score chart" summary="Shows scores over time">
        <canvas />
      </AccessibleChart>,
    );
    expect(screen.getByRole("img")).toBeInTheDocument();
  });

  it("should have aria-label", () => {
    render(
      <AccessibleChart label="Cost trend" summary="Cost increasing">
        <canvas />
      </AccessibleChart>,
    );
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Cost trend");
  });

  it("should render sr-only summary span", () => {
    render(
      <AccessibleChart label="Chart" summary="Data summary text">
        <canvas />
      </AccessibleChart>,
    );
    const srSpan = screen.getByText("Data summary text");
    expect(srSpan).toBeInTheDocument();
    expect(srSpan.className).toContain("sr-only");
  });

  it("should render children", () => {
    render(
      <AccessibleChart label="Chart" summary="Summary">
        <div data-testid="chart-child">Chart goes here</div>
      </AccessibleChart>,
    );
    expect(screen.getByTestId("chart-child")).toBeInTheDocument();
  });
});
