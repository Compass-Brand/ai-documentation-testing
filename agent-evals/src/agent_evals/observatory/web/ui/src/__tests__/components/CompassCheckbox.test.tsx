import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompassCheckbox } from "../../components/CompassCheckbox";

describe("CompassCheckbox", () => {
  it("should render with role=checkbox", () => {
    render(<CompassCheckbox checked={false} />);
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
  });

  it("should set aria-checked=false when unchecked", () => {
    render(<CompassCheckbox checked={false} />);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "false");
  });

  it("should set aria-checked=true when checked", () => {
    render(<CompassCheckbox checked={true} />);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-checked", "true");
  });

  it("should apply custom aria-label", () => {
    render(<CompassCheckbox checked={false} aria-label="Select model" />);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-label", "Select model");
  });

  it("should have default aria-label when none provided", () => {
    render(<CompassCheckbox checked={false} />);
    expect(screen.getByRole("checkbox")).toHaveAttribute("aria-label");
  });

  it("should be 20x20px (w-5 h-5)", () => {
    render(<CompassCheckbox checked={false} />);
    const el = screen.getByRole("checkbox");
    expect(el.className).toContain("w-5");
    expect(el.className).toContain("h-5");
  });

  it("should contain an SVG element", () => {
    render(<CompassCheckbox checked={true} />);
    const el = screen.getByRole("checkbox");
    expect(el.querySelector("svg")).toBeInTheDocument();
  });

  it("should contain a circle element in the SVG", () => {
    render(<CompassCheckbox checked={false} />);
    const el = screen.getByRole("checkbox");
    expect(el.querySelector("circle")).toBeInTheDocument();
  });

  it("should contain a checkmark path in the SVG", () => {
    render(<CompassCheckbox checked={true} />);
    const el = screen.getByRole("checkbox");
    expect(el.querySelector("path")).toBeInTheDocument();
  });

  it("should apply checked animation class when checked", () => {
    render(<CompassCheckbox checked={true} />);
    const el = screen.getByRole("checkbox");
    expect(el.className).toContain("compass-checkbox-checked");
  });

  it("should not apply checked animation class when unchecked", () => {
    render(<CompassCheckbox checked={false} />);
    const el = screen.getByRole("checkbox");
    expect(el.className).not.toContain("compass-checkbox-checked");
  });

  it("should call onChange when clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CompassCheckbox checked={false} onChange={onChange} />);
    await user.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("should call onChange with false when checked checkbox is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CompassCheckbox checked={true} onChange={onChange} />);
    await user.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("should not throw when clicked without onChange", async () => {
    const user = userEvent.setup();
    render(<CompassCheckbox checked={false} />);
    await expect(user.click(screen.getByRole("checkbox"))).resolves.not.toThrow();
  });

  it("should merge custom className", () => {
    render(<CompassCheckbox checked={false} className="custom-class" />);
    const el = screen.getByRole("checkbox");
    expect(el.className).toContain("custom-class");
  });

  it("should be focusable via keyboard", () => {
    render(<CompassCheckbox checked={false} />);
    const el = screen.getByRole("checkbox");
    expect(el).toHaveAttribute("tabIndex", "0");
  });

  it("should toggle on Enter key", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CompassCheckbox checked={false} onChange={onChange} />);
    const el = screen.getByRole("checkbox");
    el.focus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("should toggle on Space key", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CompassCheckbox checked={false} onChange={onChange} />);
    const el = screen.getByRole("checkbox");
    el.focus();
    await user.keyboard(" ");
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("should have no inline style attributes on any element", () => {
    const { container } = render(<CompassCheckbox checked={false} onChange={vi.fn()} />);
    const inlineStyled = container.querySelectorAll("[style]");
    expect(inlineStyled.length).toBe(0);
  });
});
