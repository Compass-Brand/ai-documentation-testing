import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Inbox } from "lucide-react";
import { EmptyState } from "../../components/EmptyState";

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("EmptyState", () => {
  it("should render title and description", () => {
    renderWithRouter(
      <EmptyState icon={Inbox} title="No data" description="Nothing here" />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("should render the icon", () => {
    const { container } = renderWithRouter(
      <EmptyState icon={Inbox} title="Empty" description="Desc" />,
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("should render CTA link when ctaLabel and ctaTo are provided", () => {
    renderWithRouter(
      <EmptyState
        icon={Inbox}
        title="No runs"
        description="Start one"
        ctaLabel="Start Run"
        ctaTo="/run"
      />,
    );
    const link = screen.getByRole("link", { name: "Start Run" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/run");
  });

  it("should not render CTA when ctaLabel is missing", () => {
    renderWithRouter(
      <EmptyState icon={Inbox} title="No runs" description="Desc" />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("should not render CTA when ctaTo is missing", () => {
    renderWithRouter(
      <EmptyState
        icon={Inbox}
        title="No runs"
        description="Desc"
        ctaLabel="Go"
      />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
