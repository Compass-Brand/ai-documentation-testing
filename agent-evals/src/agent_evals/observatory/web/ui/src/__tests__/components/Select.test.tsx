import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Select } from "../../components/Select";

const options = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
  { value: "c", label: "Gamma" },
];

describe("Select", () => {
  it("renders with the selected value text", () => {
    render(
      <Select
        options={options}
        value="b"
        onValueChange={vi.fn()}
        aria-label="Test select"
      />,
    );
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("renders placeholder when value is empty", () => {
    render(
      <Select
        options={options}
        value=""
        onValueChange={vi.fn()}
        placeholder="Pick one"
        aria-label="Test select"
      />,
    );
    expect(screen.getByText("Pick one")).toBeInTheDocument();
  });

  it("has the trigger element with correct aria-label", () => {
    render(
      <Select
        options={options}
        value="a"
        onValueChange={vi.fn()}
        aria-label="My select"
      />,
    );
    expect(screen.getByLabelText("My select")).toBeInTheDocument();
  });
});
