// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import RunConfig from "../../pages/RunConfig";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RunConfig", () => {
  it("should render the page heading", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText("Run Configuration")).toBeInTheDocument();
  });

  it("should render mode selector with Taguchi and Full options", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText("Taguchi")).toBeInTheDocument();
    expect(screen.getByText("Full")).toBeInTheDocument();
  });

  it("should render model input field", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByLabelText(/model/i)).toBeInTheDocument();
  });

  it("should render repetitions input", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByLabelText(/repetition/i)).toBeInTheDocument();
  });

  it("should have a submit button", () => {
    render(<RunConfig />, { wrapper });
    expect(
      screen.getByRole("button", { name: /start/i }),
    ).toBeInTheDocument();
  });

  it("should select Taguchi mode by default", () => {
    render(<RunConfig />, { wrapper });
    const taguchiRadio = screen.getByLabelText("Taguchi");
    expect(taguchiRadio).toBeChecked();
  });

  it("should show pipeline options when Taguchi mode is selected", () => {
    render(<RunConfig />, { wrapper });
    // Taguchi is default, so pipeline options should be visible
    expect(screen.getByLabelText(/Pipeline Mode/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Quality Type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Top-K/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Alpha/i)).toBeInTheDocument();
  });

  it("should hide pipeline options when Full mode is selected", async () => {
    render(<RunConfig />, { wrapper });
    // Click Full mode radio
    const fullRadio = screen.getByLabelText("Full");
    await userEvent.click(fullRadio);
    expect(screen.queryByLabelText(/Pipeline Mode/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Quality Type/i)).not.toBeInTheDocument();
  });
});
