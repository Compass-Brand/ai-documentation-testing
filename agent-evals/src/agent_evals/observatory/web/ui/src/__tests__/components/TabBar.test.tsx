import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TabBar } from "../../components/TabBar";

const tabs = [
  { key: "overview", label: "Overview" },
  { key: "analysis", label: "Analysis" },
  { key: "settings", label: "Settings" },
];

describe("TabBar", () => {
  it("renders all tab labels", () => {
    render(
      <TabBar tabs={tabs} activeKey="overview" onTabChange={vi.fn()} />,
    );
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("marks the active tab with aria-selected", () => {
    render(
      <TabBar tabs={tabs} activeKey="analysis" onTabChange={vi.fn()} />,
    );
    expect(screen.getByText("Analysis").closest("button")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("Overview").closest("button")).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("calls onTabChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(
      <TabBar tabs={tabs} activeKey="overview" onTabChange={onChange} />,
    );
    fireEvent.click(screen.getByText("Settings"));
    expect(onChange).toHaveBeenCalledWith("settings");
  });

  it("has tablist role on container", () => {
    render(
      <TabBar tabs={tabs} activeKey="overview" onTabChange={vi.fn()} />,
    );
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });
});
