import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../../components/Button";

describe("Button", () => {
  it("should render with children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("should apply primary variant by default", () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-brand-goldenrod");
    expect(btn.className).toContain("text-brand-charcoal");
    expect(btn.className).toContain("rounded-pill");
  });

  it("should apply secondary variant with charcoal border", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("border-brand-charcoal");
    expect(btn.className).toContain("bg-transparent");
  });

  it("should apply ghost variant with rounded-card", () => {
    render(<Button variant="ghost">Ghost</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("text-brand-slate");
    expect(btn.className).toContain("rounded-card");
  });

  it("should apply danger variant with clay background", () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-brand-clay");
    expect(btn.className).toContain("text-brand-bone");
  });

  it("should apply sm size (h-8)", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("h-8");
  });

  it("should apply md size (h-11) by default", () => {
    render(<Button>Medium</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("h-11");
  });

  it("should apply lg size (h-[52px])", () => {
    render(<Button size="lg">Large</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("h-[52px]");
  });

  it("should merge custom className", () => {
    render(<Button className="custom-class">Custom</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("custom-class");
  });

  it("should apply disabled styles", () => {
    render(<Button disabled>Disabled</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    expect(btn.className).toContain("disabled:opacity-50");
  });

  it("should have displayName", () => {
    expect(Button.displayName).toBe("Button");
  });
});
