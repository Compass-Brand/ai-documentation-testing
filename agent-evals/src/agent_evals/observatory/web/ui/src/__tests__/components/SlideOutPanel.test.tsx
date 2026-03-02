import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SlideOutPanel } from "../../components/SlideOutPanel";

describe("SlideOutPanel", () => {
  it("should render title when open", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Details">
        <p>Panel content</p>
      </SlideOutPanel>,
    );
    expect(screen.getByText("Details")).toBeInTheDocument();
  });

  it("should render children when open", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Details">
        <p>Panel content</p>
      </SlideOutPanel>,
    );
    expect(screen.getByText("Panel content")).toBeInTheDocument();
  });

  it("should have close button", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Details">
        <p>Content</p>
      </SlideOutPanel>,
    );
    const closeBtn = screen.getByRole("button");
    expect(closeBtn).toBeInTheDocument();
    expect(closeBtn.querySelector("svg")).toBeInTheDocument();
  });

  it("should default to lg width (500px)", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Test">
        <p>Content</p>
      </SlideOutPanel>,
    );
    const content = screen.getByRole("dialog");
    expect(content.className).toContain("w-[500px]");
  });

  it("should accept md width (400px)", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Test" width="md">
        <p>Content</p>
      </SlideOutPanel>,
    );
    const content = screen.getByRole("dialog");
    expect(content.className).toContain("w-[400px]");
  });

  it("should have bone background and shadow-panel", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Test">
        <p>Content</p>
      </SlideOutPanel>,
    );
    const content = screen.getByRole("dialog");
    expect(content.className).toContain("bg-brand-bone");
    expect(content.className).toContain("shadow-panel");
  });

  it("should have sticky header with mist border", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Test">
        <p>Content</p>
      </SlideOutPanel>,
    );
    const header = screen.getByText("Test").closest("div");
    expect(header?.className).toContain("sticky");
    expect(header?.className).toContain("border-brand-mist");
  });

  it("close button has focus-visible styling", () => {
    render(
      <SlideOutPanel open={true} onClose={() => {}} title="Test Panel">
        <p>content</p>
      </SlideOutPanel>,
    );
    const closeBtn = screen.getByRole("button");
    expect(closeBtn.className).toContain("focus-visible:ring-brand-goldenrod");
  });
});
