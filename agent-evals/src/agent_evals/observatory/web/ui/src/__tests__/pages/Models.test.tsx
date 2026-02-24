import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { Models } from "../../pages/Models";

// Mock hooks
vi.mock("../../api/hooks", () => ({
  useModels: vi.fn(),
  useModelDetail: vi.fn(),
  useModelEndpoints: vi.fn(),
  useGroups: vi.fn(),
  useCreateGroup: vi.fn(),
  useAddGroupMembers: vi.fn(),
  useSyncStatus: vi.fn(),
  useTriggerSync: vi.fn(),
}));

vi.mock("../../hooks/useFilterParams", () => ({
  useFilterParams: vi.fn(),
}));

// Mock CompassCheckbox
vi.mock("../../components/CompassCheckbox", () => ({
  CompassCheckbox: ({ checked }: { checked: boolean }) => (
    <div data-testid="compass-checkbox" data-checked={checked} />
  ),
}));

import {
  useModels,
  useModelDetail,
  useModelEndpoints,
  useGroups,
  useCreateGroup,
  useSyncStatus,
  useTriggerSync,
} from "../../api/hooks";
import { useFilterParams } from "../../hooks/useFilterParams";

const mockModels = [
  {
    id: "openai/gpt-4o",
    name: "GPT-4o",
    context_length: 128000,
    prompt_price: 0.000005,
    completion_price: 0.000015,
    modality: "text+image->text",
    tokenizer: "o200k_base",
    created: 1700000000,
    first_seen: 1700000000,
    last_seen: 1700100000,
    removed_at: null,
  },
  {
    id: "anthropic/claude-sonnet-4",
    name: "Claude Sonnet 4",
    context_length: 200000,
    prompt_price: 0.000003,
    completion_price: 0.000015,
    modality: "text+image->text",
    tokenizer: "claude",
    created: 1695000000,
    first_seen: 1700000000,
    last_seen: 1700100000,
    removed_at: null,
  },
];

const mockSetFilters = vi.fn();

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

beforeEach(() => {
  vi.mocked(useFilterParams).mockReturnValue([{}, mockSetFilters]);

  vi.mocked(useModels).mockReturnValue({
    data: { models: mockModels, total: 2 },
    isLoading: false,
    error: null,
  } as ReturnType<typeof useModels>);

  vi.mocked(useModelDetail).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  } as ReturnType<typeof useModelDetail>);

  vi.mocked(useModelEndpoints).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  } as ReturnType<typeof useModelEndpoints>);

  vi.mocked(useGroups).mockReturnValue({
    data: [],
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useGroups>);

  vi.mocked(useCreateGroup).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useCreateGroup>);

  vi.mocked(useSyncStatus).mockReturnValue({
    data: { total_models: 100, last_sync: Date.now() / 1000 },
    isLoading: false,
    error: null,
  } as ReturnType<typeof useSyncStatus>);

  vi.mocked(useTriggerSync).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useTriggerSync>);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Models page", () => {
  it("should render page heading", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("Models")).toBeInTheDocument();
  });

  it("should render search input in sidebar", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("should render filter sections", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("Pricing")).toBeInTheDocument();
  });

  it("should render model count", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText(/2 models/i)).toBeInTheDocument();
  });

  it("should render model data in table", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    expect(screen.getByText("Claude Sonnet 4")).toBeInTheDocument();
  });

  it("should render view toggle buttons", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByLabelText(/table view/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/card view/i)).toBeInTheDocument();
  });

  it("should switch to card view when card toggle clicked", () => {
    render(<Models />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText(/card view/i));
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
  });

  it("should show loading state", () => {
    vi.mocked(useModels).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof useModels>);
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("should have free models checkbox", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText(/free/i)).toBeInTheDocument();
  });

  it("should render toolbar with action buttons", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("Run Selected")).toBeInTheDocument();
    expect(screen.getByText("Save as Group")).toBeInTheDocument();
  });
});

describe("Models page — Copy button (Change 1)", () => {
  it("should render a copy button for each model row", () => {
    render(<Models />, { wrapper: createWrapper() });
    const copyButtons = screen.getAllByLabelText(/copy model id/i);
    expect(copyButtons).toHaveLength(2);
  });

  it("should copy the OpenRouter ID to clipboard on click", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });
    render(<Models />, { wrapper: createWrapper() });
    const copyButtons = screen.getAllByLabelText(/copy model id/i);
    fireEvent.click(copyButtons[0]);
    expect(writeText).toHaveBeenCalledWith("openrouter/openai/gpt-4o");
  });

  it("should not open panel when copy button is clicked", () => {
    render(<Models />, { wrapper: createWrapper() });
    const copyButtons = screen.getAllByLabelText(/copy model id/i);
    fireEvent.click(copyButtons[0]);
    // Panel should not open — no detail view elements
    expect(screen.queryByText("API ID")).not.toBeInTheDocument();
  });
});

describe("Models page — Name click opens panel (Change 2)", () => {
  it("should render model names as clickable links", () => {
    render(<Models />, { wrapper: createWrapper() });
    const nameLink = screen.getByText("GPT-4o");
    expect(nameLink.tagName).toBe("BUTTON");
    expect(nameLink.className).toContain("text-brand-goldenrod");
  });

  it("should open detail panel when name is clicked", () => {
    vi.mocked(useModelDetail).mockReturnValue({
      data: {
        ...mockModels[0],
        supported_params: [],
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useModelDetail>);

    render(<Models />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("GPT-4o"));
    expect(screen.getByText("API ID")).toBeInTheDocument();
  });

  it("should not open panel on general row click", () => {
    render(<Models />, { wrapper: createWrapper() });
    // Click on price cell, not on name
    const priceCell = screen.getAllByText("$5.00/M")[0];
    fireEvent.click(priceCell.closest("tr")!);
    // Panel should not open
    expect(screen.queryByText("API ID")).not.toBeInTheDocument();
  });
});

describe("Models page — Deployed column (Change 3)", () => {
  it("should render the Deployed column header", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("Deployed")).toBeInTheDocument();
  });

  it("should format the created timestamp as a locale date", () => {
    render(<Models />, { wrapper: createWrapper() });
    // 1700000000 * 1000 = Nov 14, 2023
    const formatted = new Date(1700000000 * 1000).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    expect(screen.getByText(formatted)).toBeInTheDocument();
  });

  it("should show dash for models without created date", () => {
    vi.mocked(useModels).mockReturnValue({
      data: {
        models: [{ ...mockModels[0], created: 0 }],
        total: 1,
      },
      isLoading: false,
      error: null,
    } as ReturnType<typeof useModels>);

    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });
});

describe("Models page — Multi-select (Change 4)", () => {
  it("should not show checkboxes by default", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.queryByTestId("compass-checkbox")).not.toBeInTheDocument();
  });

  it("should select a row on click and show checkbox", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(screen.getByTestId("compass-checkbox")).toBeInTheDocument();
  });

  it("should highlight selected row with goldenrod background", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(row.className).toContain("bg-brand-goldenrod/10");
  });

  it("should show selection count in toolbar when rows selected", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("should deselect row on second click", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.click(row);
    expect(screen.queryByText("1 selected")).not.toBeInTheDocument();
  });

  it("should support selecting multiple rows", () => {
    render(<Models />, { wrapper: createWrapper() });
    const rows = screen.getAllByRole("row").slice(1); // skip header
    fireEvent.click(rows[0]);
    fireEvent.click(rows[1]);
    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("should show Clear button when rows are selected", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });

  it("should clear selection when Clear button clicked", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    fireEvent.click(screen.getByText("Clear"));
    expect(screen.queryByTestId("compass-checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText("1 selected")).not.toBeInTheDocument();
  });

  it("should clear selection on Escape key", () => {
    render(<Models />, { wrapper: createWrapper() });
    const row = screen.getByText("$5.00/M").closest("tr")!;
    fireEvent.click(row);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("1 selected")).not.toBeInTheDocument();
  });
});
