import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AnimatedNumber } from "../../components/AnimatedNumber";

describe("AnimatedNumber", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("should render the initial value", () => {
    render(<AnimatedNumber value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("should apply format function", () => {
    render(
      <AnimatedNumber value={0.5} format={(n) => `${(n * 100).toFixed(0)}%`} />,
    );
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("should jump instantly when prefers-reduced-motion is set", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: true,
      media: "",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });

    const { rerender } = render(<AnimatedNumber value={0} />);
    rerender(<AnimatedNumber value={100} />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("should animate via requestAnimationFrame when motion is allowed", () => {
    const rafSpy = vi.spyOn(window, "requestAnimationFrame");

    const { rerender } = render(<AnimatedNumber value={0} />);
    act(() => {
      rerender(<AnimatedNumber value={100} />);
    });

    expect(rafSpy).toHaveBeenCalled();
  });

  it("should cancel animation on unmount", () => {
    const cancelSpy = vi.spyOn(window, "cancelAnimationFrame");

    const { rerender, unmount } = render(<AnimatedNumber value={0} />);
    act(() => {
      rerender(<AnimatedNumber value={100} />);
    });
    unmount();

    expect(cancelSpy).toHaveBeenCalled();
  });

  it("should render a span element", () => {
    const { container } = render(<AnimatedNumber value={5} />);
    expect(container.querySelector("span")).toBeInTheDocument();
  });
});
