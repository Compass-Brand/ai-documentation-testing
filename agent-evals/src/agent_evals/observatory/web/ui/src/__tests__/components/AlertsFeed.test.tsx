import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AlertsFeed, type AlertItem } from "../../components/AlertsFeed";

describe("AlertsFeed", () => {
  it("should show empty message when no alerts", () => {
    render(<AlertsFeed alerts={[]} />);
    expect(screen.getByText("No alerts.")).toBeInTheDocument();
  });

  it("should render alert items", () => {
    const alerts: AlertItem[] = [
      {
        type: "anomaly_alert",
        message: "Cost anomaly on claude: $0.080 (4.0x average)",
        timestamp: new Date("2026-02-24T10:00:00Z"),
      },
    ];
    render(<AlertsFeed alerts={alerts} />);
    expect(screen.getByText(/Cost anomaly/)).toBeInTheDocument();
  });

  it("should show XCircle icon for budget exceeded alerts", () => {
    const alerts: AlertItem[] = [
      {
        type: "model_budget_exceeded",
        message: "Budget exceeded for claude",
        timestamp: new Date(),
      },
    ];
    const { container } = render(<AlertsFeed alerts={alerts} />);
    // XCircle renders an SVG — check for the error background class
    const alertDiv = container.querySelector(".bg-brand-clay\\/5");
    expect(alertDiv).toBeTruthy();
  });

  it("should show AlertTriangle icon for non-budget alerts", () => {
    const alerts: AlertItem[] = [
      {
        type: "anomaly_alert",
        message: "Cost anomaly",
        timestamp: new Date(),
      },
    ];
    const { container } = render(<AlertsFeed alerts={alerts} />);
    const alertDiv = container.querySelector(".bg-brand-amber\\/5");
    expect(alertDiv).toBeTruthy();
  });

  it("should have role=log for accessibility", () => {
    const alerts: AlertItem[] = [
      {
        type: "anomaly_alert",
        message: "Test alert",
        timestamp: new Date(),
      },
    ];
    render(<AlertsFeed alerts={alerts} />);
    expect(screen.getByRole("log")).toBeInTheDocument();
  });
});
