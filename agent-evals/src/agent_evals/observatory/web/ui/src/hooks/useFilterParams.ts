import { useSearchParams } from "react-router-dom";
import { useMemo, useCallback } from "react";
import type { ModelFilters } from "../api/client";

function parseNum(params: URLSearchParams, key: string): number | undefined {
  const raw = params.get(key);
  if (raw == null) return undefined;
  const n = Number(raw);
  return Number.isNaN(n) ? undefined : n;
}

export function useFilterParams(): [
  ModelFilters,
  (f: Partial<ModelFilters>) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo<ModelFilters>(
    () => ({
      search: searchParams.get("search") ?? undefined,
      free: searchParams.get("free") === "true" || undefined,
      maxPrice: parseNum(searchParams, "max_price"),
      minContext: parseNum(searchParams, "min_context"),
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
          if (val === undefined || val === null || val === "" || val === false) {
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
