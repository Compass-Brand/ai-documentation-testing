// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("should render without crashing", () => {
    renderWithProviders();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("should display the Observatory brand title", () => {
    renderWithProviders();
    const allObservatory = screen.getAllByText("Observatory");
    expect(allObservatory.length).toBeGreaterThanOrEqual(1);
    // The first is the brand title span
    expect(allObservatory[0].tagName).toBe("SPAN");
  });

  it("should render all six nav links", () => {
    renderWithProviders();
    expect(screen.getByText("Run Config")).toBeInTheDocument();
    expect(screen.getByText("Live Monitor")).toBeInTheDocument();
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Models")).toBeInTheDocument();
  });
});
