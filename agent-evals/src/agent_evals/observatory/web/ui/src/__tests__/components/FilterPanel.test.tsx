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

  it("should render children when open", () => {
    render(
      <FilterSection label="Pricing" defaultOpen>
        <div>Filter content</div>
      </FilterSection>,
    );
    expect(screen.getByText("Filter content")).toBeInTheDocument();
  });

  it("should hide children by default", () => {
    render(
      <FilterSection label="Pricing">
        <div>Filter content</div>
      </FilterSection>,
    );
    expect(screen.queryByText("Filter content")).not.toBeInTheDocument();
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

  it("should render as a button with aria-expanded=false by default", () => {
    render(
      <FilterSection label="Pricing">
        <div>Content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("should render as a button with aria-expanded=true when defaultOpen", () => {
    render(
      <FilterSection label="Pricing" defaultOpen>
        <div>Content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(button).toHaveAttribute("aria-expanded", "true");
  });

  it("should show children when defaultOpen is true", () => {
    render(
      <FilterSection label="Pricing" defaultOpen>
        <div>Visible content</div>
      </FilterSection>,
    );
    expect(screen.getByText("Visible content")).toBeInTheDocument();
  });

  it("should toggle children visibility on click", () => {
    render(
      <FilterSection label="Pricing">
        <div>Toggle content</div>
      </FilterSection>,
    );
    const button = screen.getByRole("button", { name: /pricing/i });
    expect(screen.queryByText("Toggle content")).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.getByText("Toggle content")).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(button);
    expect(screen.queryByText("Toggle content")).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("should render chevron icon that rotates when open", () => {
    render(
      <FilterSection label="Pricing" defaultOpen>
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
  it("should render two range inputs (low and high)", () => {
    render(
      <FilterRange
        label="Max Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(2);
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

  it("should have dual-range-thumb class", () => {
    render(
      <FilterRange
        label="Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    const sliders = screen.getAllByRole("slider");
    sliders.forEach((slider) => {
      expect(slider.className).toContain("dual-range-thumb");
    });
  });

  it("should have aria-labels for min and max", () => {
    render(
      <FilterRange
        label="Max Price"
        min={0}
        max={100}
        value={[0, 50]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("slider", { name: "Max Price minimum" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Max Price maximum" })).toBeInTheDocument();
  });

  it("should call onChange when high value changes", () => {
    vi.useFakeTimers();
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
    fireEvent.change(screen.getByRole("slider", { name: "Price maximum" }), { target: { value: "75" } });
    vi.advanceTimersByTime(200);
    expect(onChange).toHaveBeenCalledWith([0, 75]);
    vi.useRealTimers();
  });
});
