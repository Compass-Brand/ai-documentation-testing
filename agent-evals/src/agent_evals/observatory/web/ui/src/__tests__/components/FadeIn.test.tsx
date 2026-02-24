import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FadeIn } from "../../components/FadeIn";

describe("FadeIn", () => {
  it("should render children", () => {
    render(<FadeIn><span>Hello</span></FadeIn>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("should apply animate-fade-in-up class", () => {
    render(<FadeIn><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.className).toContain("animate-fade-in-up");
  });

  it("should start with opacity-0", () => {
    render(<FadeIn><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.className).toContain("opacity-0");
  });

  it("should apply 50ms stagger delay based on index", () => {
    render(<FadeIn delay={3}><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.style.animationDelay).toBe("150ms");
  });

  it("should default to 0 delay", () => {
    render(<FadeIn><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.style.animationDelay).toBe("0ms");
  });

  it("should use forwards fill mode", () => {
    render(<FadeIn><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.style.animationFillMode).toBe("forwards");
  });

  it("should merge custom className", () => {
    render(<FadeIn className="extra"><span>Content</span></FadeIn>);
    const wrapper = screen.getByText("Content").parentElement!;
    expect(wrapper.className).toContain("extra");
  });
});
