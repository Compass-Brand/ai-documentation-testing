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
