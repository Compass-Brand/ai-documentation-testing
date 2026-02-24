import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

function createWrapper(initialEntries: string[] = ["/"]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      MemoryRouter,
      { initialEntries },
      children,
    );
  };
}

describe("useFilterParams", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("should return empty filters when no URL params", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper();

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;

    expect(filters.search).toBeUndefined();
    expect(filters.free).toBeUndefined();
    expect(filters.maxPrice).toBeUndefined();
    expect(filters.minContext).toBeUndefined();
    expect(filters.modality).toBeUndefined();
    expect(filters.capability).toBeUndefined();
    expect(filters.tokenizer).toBeUndefined();
    expect(filters.sort).toBeUndefined();
  });

  it("should read search param from URL", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper(["/?search=claude"]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;

    expect(filters.search).toBe("claude");
  });

  it("should read free=true from URL", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper(["/?free=true"]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;

    expect(filters.free).toBe(true);
  });

  it("should read numeric params from URL", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper(["/?max_price=10&min_context=8000"]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;

    expect(filters.maxPrice).toBe(10);
    expect(filters.minContext).toBe(8000);
  });

  it("should read all string params from URL", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper([
      "/?modality=text&capability=tools&tokenizer=cl100k&sort=price",
    ]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });
    const [filters] = result.current;

    expect(filters.modality).toBe("text");
    expect(filters.capability).toBe("tools");
    expect(filters.tokenizer).toBe("cl100k");
    expect(filters.sort).toBe("price");
  });

  it("should update URL params via setFilters", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper();

    const { result } = renderHook(() => useFilterParams(), { wrapper });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ search: "gpt", free: true });
    });

    const [filters] = result.current;
    expect(filters.search).toBe("gpt");
    expect(filters.free).toBe(true);
  });

  it("should remove params when set to null/empty/false", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper(["/?search=claude&free=true"]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ search: "", free: false });
    });

    const [filters] = result.current;
    expect(filters.search).toBeUndefined();
    expect(filters.free).toBeUndefined();
  });

  it("should merge partial updates without removing other params", async () => {
    const { useFilterParams } = await import("../../hooks/useFilterParams");
    const wrapper = createWrapper(["/?search=claude&modality=text"]);

    const { result } = renderHook(() => useFilterParams(), { wrapper });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ sort: "price" });
    });

    const [filters] = result.current;
    expect(filters.search).toBe("claude");
    expect(filters.modality).toBe("text");
    expect(filters.sort).toBe("price");
  });
});
