// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../components/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { StatusBadge } from "../components/StatusBadge";
import { StatusDot } from "../components/StatusDot";
import { FadeIn } from "../components/FadeIn";
import { AccessibleChart } from "../components/AccessibleChart";

describe("Button", () => {
  it("should render with default variant and size", () => {
    render(<Button>Click me</Button>);
    const btn = screen.getByRole("button", { name: "Click me" });
    expect(btn).toBeInTheDocument();
    expect(btn.className).toContain("rounded-pill");
  });

  it("should apply primary variant classes", () => {
    render(<Button variant="primary">Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-brand-goldenrod");
  });

  it("should apply danger variant classes", () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-brand-clay");
  });

  it("should apply ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("text-brand-slate");
  });

  it("should apply lg size with 52px height", () => {
    render(<Button size="lg">Large</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("h-[52px]");
  });

  it("should render as child when asChild is true", () => {
    render(
      <Button asChild>
        <a href="/test">Link button</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Link button" });
    expect(link).toBeInTheDocument();
  });
});

describe("Card", () => {
  it("should render with card styling", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card.className).toContain("rounded-card");
    expect(card.className).toContain("shadow-card");
  });

  it("should render CardHeader, CardTitle, CardContent", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
        </CardHeader>
        <CardContent>Body</CardContent>
      </Card>,
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });
});

describe("Input", () => {
  it("should render with brand styling", () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText("Enter text");
    expect(input).toBeInTheDocument();
    expect(input.className).toContain("rounded-card");
    expect(input.className).toContain("border-brand-mist");
  });
});

describe("StatusBadge", () => {
  it("should render success badge", () => {
    render(<StatusBadge status="success" label="Passed" />);
    const badge = screen.getByText("Passed");
    expect(badge.className).toContain("text-brand-sage");
  });

  it("should render error badge", () => {
    render(<StatusBadge status="error" label="Failed" />);
    const badge = screen.getByText("Failed");
    expect(badge.className).toContain("text-brand-clay");
  });

  it("should render new badge with goldenrod background", () => {
    render(<StatusBadge status="new" label="New" />);
    const badge = screen.getByText("New");
    expect(badge.className).toContain("bg-brand-goldenrod");
  });
});

describe("StatusDot", () => {
  it("should render with success color", () => {
    render(<StatusDot status="success" />);
    const dot = screen.getByRole("status");
    expect(dot.className).toContain("bg-brand-sage");
  });

  it("should render with aria-label", () => {
    render(<StatusDot status="error" />);
    const dot = screen.getByRole("status");
    expect(dot).toHaveAttribute("aria-label", "error");
  });

  it("should pulse for syncing status", () => {
    render(<StatusDot status="syncing" />);
    const dot = screen.getByRole("status");
    expect(dot.className).toContain("animate-pulse");
  });
});

describe("FadeIn", () => {
  it("should render children", () => {
    render(<FadeIn>Hello</FadeIn>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("should apply animation class", () => {
    render(<FadeIn><span>Content</span></FadeIn>);
    const el = screen.getByText("Content").parentElement!;
    expect(el.className).toContain("animate-fade-in-up");
  });

  it("should apply stagger delay via style", () => {
    render(<FadeIn delay={2}><span>Delayed</span></FadeIn>);
    const el = screen.getByText("Delayed").parentElement!;
    expect(el.style.animationDelay).toBe("100ms");
  });
});

describe("AccessibleChart", () => {
  it("should render with aria-label", () => {
    render(
      <AccessibleChart label="Score chart" summary="Shows scores over time">
        <div>Chart content</div>
      </AccessibleChart>,
    );
    const wrapper = screen.getByRole("img", { name: "Score chart" });
    expect(wrapper).toBeInTheDocument();
  });

  it("should include sr-only summary", () => {
    render(
      <AccessibleChart label="Test" summary="Test summary">
        <div />
      </AccessibleChart>,
    );
    expect(screen.getByText("Test summary")).toBeInTheDocument();
  });
});
