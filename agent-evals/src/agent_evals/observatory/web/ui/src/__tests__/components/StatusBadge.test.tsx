import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../../components/StatusBadge";

describe("StatusBadge", () => {
  it("should render label text", () => {
    render(<StatusBadge status="success" label="Passed" />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("should apply success styles (sage)", () => {
    render(<StatusBadge status="success" label="OK" />);
    const badge = screen.getByText("OK");
    expect(badge.className).toContain("bg-brand-sage/15");
    expect(badge.className).toContain("text-brand-sage");
  });

  it("should apply warning styles (amber)", () => {
    render(<StatusBadge status="warning" label="Warn" />);
    const badge = screen.getByText("Warn");
    expect(badge.className).toContain("bg-brand-amber/15");
    expect(badge.className).toContain("text-brand-amber");
  });

  it("should apply error styles (clay)", () => {
    render(<StatusBadge status="error" label="Fail" />);
    const badge = screen.getByText("Fail");
    expect(badge.className).toContain("bg-brand-clay/15");
    expect(badge.className).toContain("text-brand-clay");
  });

  it("should apply neutral styles (slate)", () => {
    render(<StatusBadge status="neutral" label="N/A" />);
    const badge = screen.getByText("N/A");
    expect(badge.className).toContain("bg-brand-slate/15");
    expect(badge.className).toContain("text-brand-slate");
  });

  it("should apply active styles (goldenrod)", () => {
    render(<StatusBadge status="active" label="Running" />);
    const badge = screen.getByText("Running");
    expect(badge.className).toContain("bg-brand-goldenrod/15");
    expect(badge.className).toContain("text-brand-goldenrod");
  });

  it("should apply new styles (solid goldenrod)", () => {
    render(<StatusBadge status="new" label="New" />);
    const badge = screen.getByText("New");
    expect(badge.className).toContain("bg-brand-goldenrod");
    expect(badge.className).toContain("text-brand-charcoal");
  });

  it("should have pill shape and caption text", () => {
    render(<StatusBadge status="success" label="Test" />);
    const badge = screen.getByText("Test");
    expect(badge.className).toContain("rounded-pill");
    expect(badge.className).toContain("text-caption");
  });

  it("should merge custom className", () => {
    render(<StatusBadge status="success" label="Test" className="ml-2" />);
    expect(screen.getByText("Test").className).toContain("ml-2");
  });
});
