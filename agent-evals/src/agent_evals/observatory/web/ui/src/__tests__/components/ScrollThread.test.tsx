import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScrollThread } from "../../components/ScrollThread";

describe("ScrollThread", () => {
  it("should render a fixed left-0 container", () => {
    const { container } = render(<ScrollThread />);
    const track = container.firstElementChild as HTMLElement;
    expect(track.className).toContain("fixed");
    expect(track.className).toContain("left-0");
  });

  it("should have 2px wide track with mist background", () => {
    const { container } = render(<ScrollThread />);
    const track = container.firstElementChild as HTMLElement;
    expect(track.className).toContain("w-[2px]");
    expect(track.className).toContain("bg-brand-mist");
  });

  it("should have goldenrod fill indicator", () => {
    const { container } = render(<ScrollThread />);
    const track = container.firstElementChild as HTMLElement;
    const fill = track.firstElementChild as HTMLElement;
    expect(fill.className).toContain("bg-brand-goldenrod");
  });

  it("should start with 0% fill height", () => {
    const { container } = render(<ScrollThread />);
    const track = container.firstElementChild as HTMLElement;
    const fill = track.firstElementChild as HTMLElement;
    expect(fill.style.height).toBe("0%");
  });
});
