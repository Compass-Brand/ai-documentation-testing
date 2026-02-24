import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "../../components/Input";

describe("Input", () => {
  it("should render an input element", () => {
    render(<Input aria-label="test" />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("should have h-11 height", () => {
    render(<Input aria-label="test" />);
    expect(screen.getByRole("textbox").className).toContain("h-11");
  });

  it("should have rounded-card border radius", () => {
    render(<Input aria-label="test" />);
    expect(screen.getByRole("textbox").className).toContain("rounded-card");
  });

  it("should have mist border and bone background", () => {
    render(<Input aria-label="test" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-brand-mist");
    expect(input.className).toContain("bg-brand-bone");
  });

  it("should have goldenrod focus ring", () => {
    render(<Input aria-label="test" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("focus:border-brand-goldenrod");
    expect(input.className).toContain("focus:ring-brand-goldenrod/20");
  });

  it("should have placeholder slate/60 style", () => {
    render(<Input aria-label="test" placeholder="Search..." />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("placeholder:text-brand-slate/60");
  });

  it("should handle disabled state", () => {
    render(<Input aria-label="test" disabled />);
    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
    expect(input.className).toContain("disabled:opacity-50");
  });

  it("should merge custom className", () => {
    render(<Input aria-label="test" className="w-64" />);
    expect(screen.getByRole("textbox").className).toContain("w-64");
  });

  it("should have displayName", () => {
    expect(Input.displayName).toBe("Input");
  });
});
