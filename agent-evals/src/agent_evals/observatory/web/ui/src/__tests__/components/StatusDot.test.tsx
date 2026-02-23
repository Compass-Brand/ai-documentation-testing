import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusDot } from "../../components/StatusDot";

describe("StatusDot", () => {
  it("should render with role=status", () => {
    render(<StatusDot status="success" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("should have aria-label matching status", () => {
    render(<StatusDot status="error" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "error");
  });

  it("should be 8px (h-2 w-2) circle", () => {
    render(<StatusDot status="success" />);
    const dot = screen.getByRole("status");
    expect(dot.className).toContain("h-2");
    expect(dot.className).toContain("w-2");
    expect(dot.className).toContain("rounded-full");
  });

  it("should use sage color for success", () => {
    render(<StatusDot status="success" />);
    expect(screen.getByRole("status").className).toContain("bg-brand-sage");
  });

  it("should use amber with pulse for warning", () => {
    render(<StatusDot status="warning" />);
    const dot = screen.getByRole("status");
    expect(dot.className).toContain("bg-brand-amber");
    expect(dot.className).toContain("animate-pulse");
  });

  it("should use clay for error", () => {
    render(<StatusDot status="error" />);
    expect(screen.getByRole("status").className).toContain("bg-brand-clay");
  });

  it("should use amber with pulse for syncing", () => {
    render(<StatusDot status="syncing" />);
    const dot = screen.getByRole("status");
    expect(dot.className).toContain("bg-brand-amber");
    expect(dot.className).toContain("animate-pulse");
  });

  it("should use slate for offline", () => {
    render(<StatusDot status="offline" />);
    expect(screen.getByRole("status").className).toContain("bg-brand-slate");
  });
});
