import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/Card";

describe("Card", () => {
  it("should render with bone background and shadow", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card.className).toContain("bg-brand-bone");
    expect(card.className).toContain("rounded-card");
    expect(card.className).toContain("shadow-card");
  });

  it("should have hover shadow transition", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card.className).toContain("hover:shadow-card-hover");
  });

  it("should have p-sp-6 padding", () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId("card");
    expect(card.className).toContain("p-sp-6");
  });

  it("should merge custom className", () => {
    render(<Card data-testid="card" className="extra">Content</Card>);
    expect(screen.getByTestId("card").className).toContain("extra");
  });

  it("should have displayName", () => {
    expect(Card.displayName).toBe("Card");
  });
});

describe("CardHeader", () => {
  it("should render with margin bottom", () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    expect(screen.getByTestId("header").className).toContain("mb-sp-4");
  });

  it("should have displayName", () => {
    expect(CardHeader.displayName).toBe("CardHeader");
  });
});

describe("CardTitle", () => {
  it("should render as h3 with brand styles", () => {
    render(<CardTitle>Title</CardTitle>);
    const title = screen.getByRole("heading", { level: 3 });
    expect(title).toHaveTextContent("Title");
    expect(title.className).toContain("text-h4");
    expect(title.className).toContain("text-brand-charcoal");
  });

  it("should have displayName", () => {
    expect(CardTitle.displayName).toBe("CardTitle");
  });
});

describe("CardContent", () => {
  it("should render with body text styles", () => {
    render(<CardContent data-testid="content">Body</CardContent>);
    const content = screen.getByTestId("content");
    expect(content.className).toContain("text-body");
    expect(content.className).toContain("text-brand-slate");
  });

  it("should have displayName", () => {
    expect(CardContent.displayName).toBe("CardContent");
  });
});
