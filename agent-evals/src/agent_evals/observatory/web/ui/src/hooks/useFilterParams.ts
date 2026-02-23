import { useSearchParams } from "react-router-dom";
import { useMemo, useCallback } from "react";
import type { ModelFilters } from "../api/client";

export function useFilterParams(): [
  ModelFilters,
  (f: Partial<ModelFilters>) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo<ModelFilters>(
    () => ({
      search: searchParams.get("search") ?? undefined,
      free: searchParams.get("free") === "true" || undefined,
      maxPrice: searchParams.has("max_price")
        ? Number(searchParams.get("max_price"))
        : undefined,
      minContext: searchParams.has("min_context")
        ? Number(searchParams.get("min_context"))
        : undefined,
      modality: searchParams.get("modality") ?? undefined,
      capability: searchParams.get("capability") ?? undefined,
      tokenizer: searchParams.get("tokenizer") ?? undefined,
      sort: searchParams.get("sort") ?? undefined,
    }),
    [searchParams],
  );

  const setFilters = useCallback(
    (updates: Partial<ModelFilters>) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, val] of Object.entries(updates)) {
          if (val == null || val === "" || val === false) {
            next.delete(key);
          } else {
            next.set(key, String(val));
          }
        }
        return next;
      });
    },
    [setSearchParams],
  );

  return [filters, setFilters];
}
