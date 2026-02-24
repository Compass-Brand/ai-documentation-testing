import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton } from "../../components/Skeleton";

describe("Skeleton", () => {
  it("should render a text skeleton by default", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("h-4");
    expect(el.className).toContain("w-full");
    expect(el.className).toContain("shimmer");
  });

  it("should render a card skeleton", () => {
    const { container } = render(<Skeleton variant="card" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("h-32");
    expect(el.className).toContain("rounded-card");
  });

  it("should render a chart skeleton", () => {
    const { container } = render(<Skeleton variant="chart" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("h-64");
    expect(el.className).toContain("rounded-card");
  });

  it("should render a circle skeleton", () => {
    const { container } = render(<Skeleton variant="circle" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("h-10");
    expect(el.className).toContain("w-10");
    expect(el.className).toContain("rounded-full");
  });

  it("should be aria-hidden", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("should apply bg-brand-mist base class", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstElementChild!.className).toContain("bg-brand-mist");
  });

  it("should merge custom className", () => {
    const { container } = render(<Skeleton className="my-custom" />);
    expect(container.firstElementChild!.className).toContain("my-custom");
  });
});
