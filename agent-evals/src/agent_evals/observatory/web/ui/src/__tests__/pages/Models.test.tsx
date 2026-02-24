import { describe, it, expect, vi, beforeEach } from "vitest";
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
    prompt_price: 0.005,
    completion_price: 0.015,
    modality: "text+image->text",
    tokenizer: "o200k_base",
    first_seen: 1700000000,
    last_seen: 1700100000,
    removed_at: null,
  },
  {
    id: "anthropic/claude-sonnet-4",
    name: "Claude Sonnet 4",
    context_length: 200000,
    prompt_price: 0.003,
    completion_price: 0.015,
    modality: "text+image->text",
    tokenizer: "claude",
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
    // In card view we should see model cards, not a table
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
