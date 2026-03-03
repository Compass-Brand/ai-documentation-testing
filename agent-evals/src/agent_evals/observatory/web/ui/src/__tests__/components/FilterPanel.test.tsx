import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  FilterSection,
  FilterCheckbox,
  FilterRange,
} from "../../components/FilterPanel";

describe("FilterSection", () => {
  it("should render label as heading", () => {
    render(
      <FilterSection label="Pricing">
        <div>Filters here</div>
      </FilterSection>,
    );
    expect(screen.getByText("Pricing")).toBeInTheDocument();
  });

  it("should render children", () => {
    render(
      <FilterSection label="Pricing">
        <div>Filter content</div>
      </FilterSection>,
    );
    expect(screen.getByText("Filter content")).toBeInTheDocument();
  });

  it("should have body-sm font-medium heading", () => {
    render(
      <FilterSection label="Test">
        <div>Content</div>
      </FilterSection>,
    );
    const heading = screen.getByText("Test");
    expect(heading.className).toContain("text-body-sm");
    expect(heading.className).toContain("font-medium");
  });

  it("should render as a button with aria-expanded", () => {
    render(
      <FilterSection label="Pricing">
        <div>Content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(button).toHaveAttribute("aria-expanded", "true");
  });

  it("should default to open and show children", () => {
    render(
      <FilterSection label="Pricing">
        <div>Visible content</div>
      </FilterSection>,
    );
    expect(screen.getByText("Visible content")).toBeInTheDocument();
  });

  it("should hide children when defaultOpen is false", () => {
    render(
      <FilterSection label="Pricing" defaultOpen={false}>
        <div>Hidden content</div>
      </FilterSection>,
    );
    expect(screen.queryByText("Hidden content")).not.toBeInTheDocument();
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("should toggle children visibility on click", () => {
    render(
      <FilterSection label="Pricing">
        <div>Toggle content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(screen.getByText("Toggle content")).toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.queryByText("Toggle content")).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);
    expect(screen.getByText("Toggle content")).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "true");
  });

  it("should render chevron icon that rotates when open", () => {
    render(
      <FilterSection label="Pricing">
        <div>Content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    const svg = button.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.className.baseVal || svg?.getAttribute("class") || "").toContain("rotate-180");
  });

  it("should not rotate chevron when collapsed", () => {
    render(
      <FilterSection label="Pricing" defaultOpen={false}>
        <div>Content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    const svg = button.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.className.baseVal || svg?.getAttribute("class") || "").not.toContain("rotate-180");
  });
});

describe("FilterCheckbox", () => {
  it("should render label text", () => {
    render(
      <FilterCheckbox label="Free models" checked={false} onCheckedChange={() => {}} />,
    );
    expect(screen.getByText("Free models")).toBeInTheDocument();
  });

  it("should reflect checked state", () => {
    render(
      <FilterCheckbox label="Free" checked={true} onCheckedChange={() => {}} />,
    );
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toHaveAttribute("data-state", "checked");
  });

  it("should call onCheckedChange when toggled", () => {
    const onChange = vi.fn();
    render(
      <FilterCheckbox label="Free" checked={false} onCheckedChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("should have goldenrod checked styling class", () => {
    render(
      <FilterCheckbox label="Free" checked={true} onCheckedChange={() => {}} />,
    );
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox.className).toContain("data-[state=checked]:bg-brand-goldenrod");
  });
});

describe("FilterRange", () => {
  it("should render range input", () => {
    render(
      <FilterRange
        label="Max Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("slider")).toBeInTheDocument();
  });

  it("should show formatted values", () => {
    render(
      <FilterRange
        label="Price"
        min={0}
        max={100}
        value={[10, 80]}
        onChange={() => {}}
        format={(n) => `$${n}`}
      />,
    );
    expect(screen.getByText("$10")).toBeInTheDocument();
    expect(screen.getByText("$80")).toBeInTheDocument();
  });

  it("should have accent-brand-goldenrod", () => {
    render(
      <FilterRange
        label="Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("slider").className).toContain("accent-brand-goldenrod");
  });

  it("should have aria-label", () => {
    render(
      <FilterRange
        label="Max Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("slider")).toHaveAttribute("aria-label", "Max Price");
  });

  it("should call onChange when value changes", () => {
    const onChange = vi.fn();
    render(
      <FilterRange
        label="Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByRole("slider"), { target: { value: "75" } });
    expect(onChange).toHaveBeenCalledWith([0, 75]);
  });
});
