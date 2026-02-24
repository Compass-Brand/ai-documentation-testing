// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

const mockStartRun = vi.fn();
const mockGetActiveRuns = vi.fn();

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual("../../api/client");
  return {
    ...actual,
    api: {
      ...(actual as Record<string, unknown>).api,
      startRun: (...args: unknown[]) => mockStartRun(...args),
      getActiveRuns: () => mockGetActiveRuns(),
    },
  };
});

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RunConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetActiveRuns.mockResolvedValue({ runs: [], count: 0 });
  });

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

  it("should show help text for Taguchi mode card", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/orthogonal arrays/i)).toBeInTheDocument();
  });

  it("should show help text for Full mode card", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/every combination of variants/i)).toBeInTheDocument();
  });

  it("should show help text for Model field", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/openrouter format/i)).toBeInTheDocument();
  });

  it("should show help text for Repetitions field", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/statistical reliability/i)).toBeInTheDocument();
  });

  it("should show help text for Task Limit field", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/355 tasks/i)).toBeInTheDocument();
  });

  it("should show help text for OA Override field", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/auto-select based on factor count/i)).toBeInTheDocument();
  });

  it("should show help text for Taguchi-only fields", () => {
    render(<RunConfig />, { wrapper });
    expect(screen.getByText(/pauses between phases/i)).toBeInTheDocument();
    expect(screen.getByText(/signal-to-noise ratio/i)).toBeInTheDocument();
    expect(screen.getByText(/refinement phase/i)).toBeInTheDocument();
    expect(screen.getByText(/95% confidence/i)).toBeInTheDocument();
  });

  it("should show error when submitting without model", async () => {
    render(<RunConfig />, { wrapper });
    const button = screen.getByRole("button", { name: /start/i });
    await userEvent.click(button);
    expect(screen.getByText("Model is required")).toBeInTheDocument();
    expect(mockStartRun).not.toHaveBeenCalled();
  });

  it("should call startRun API on submit with model", async () => {
    mockStartRun.mockResolvedValue({ run_id: "abc123", status: "started" });
    render(<RunConfig />, { wrapper });

    const modelInput = screen.getByLabelText(/model/i);
    await userEvent.type(modelInput, "openrouter/anthropic/claude-sonnet-4");

    const button = screen.getByRole("button", { name: /start/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(mockStartRun).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "taguchi",
          model: "openrouter/anthropic/claude-sonnet-4",
          repetitions: 3,
          task_limit: 0,
        }),
      );
    });
  });

  it("should navigate to live monitor on successful start", async () => {
    mockStartRun.mockResolvedValue({ run_id: "abc123", status: "started" });
    render(<RunConfig />, { wrapper });

    const modelInput = screen.getByLabelText(/model/i);
    await userEvent.type(modelInput, "test-model");

    const button = screen.getByRole("button", { name: /start/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/live?run_id=abc123");
    });
  });

  it("should show error message on API failure", async () => {
    mockStartRun.mockRejectedValue(new Error("API 500: Internal server error"));
    render(<RunConfig />, { wrapper });

    const modelInput = screen.getByLabelText(/model/i);
    await userEvent.type(modelInput, "test-model");

    const button = screen.getByRole("button", { name: /start/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/Internal server error/)).toBeInTheDocument();
    });
  });

  it("should show active run count when runs are in progress", async () => {
    mockGetActiveRuns.mockResolvedValue({
      runs: [{ run_id: "existing", mode: "taguchi", models: ["m"], started_at: "2026-01-01T00:00:00Z" }],
      count: 1,
    });
    render(<RunConfig />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/1 run currently in progress/i)).toBeInTheDocument();
    });
  });
});
