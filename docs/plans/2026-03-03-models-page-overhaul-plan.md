# Models Page Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix bugs, add features, and visually polish the Observatory Models page that browses OpenRouter models.

**Architecture:** The Models page is a React 18 SPA (Vite + TypeScript + Tailwind) backed by a Python FastAPI server with SQLite. The frontend uses TanStack Table + Query, Radix UI primitives, and a custom design system. Changes span both the frontend (UI components) and backend (new API route for provider endpoints).

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3.4, TanStack Table/Query/Virtual, Radix UI, FastAPI, SQLite, httpx

**Design doc:** `docs/plans/2026-03-03-models-page-overhaul-design.md`

---

## Key File Paths

| Alias | Path |
|-------|------|
| `MODELS_PAGE` | `agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx` |
| `MODELS_TEST` | `agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx` |
| `DATA_TABLE` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/DataTable.tsx` |
| `DATA_TABLE_TEST` | `agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/components/DataTable.test.tsx` |
| `FILTER_PANEL` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/FilterPanel.tsx` |
| `SLIDE_OUT` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx` |
| `CARD` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/Card.tsx` |
| `INPUT` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/Input.tsx` |
| `STATUS_BADGE` | `agent-evals/src/agent_evals/observatory/web/ui/src/components/StatusBadge.tsx` |
| `API_CLIENT` | `agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts` |
| `API_HOOKS` | `agent-evals/src/agent_evals/observatory/web/ui/src/api/hooks.ts` |
| `FILTER_HOOK` | `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useFilterParams.ts` |
| `UTILS` | `agent-evals/src/agent_evals/observatory/web/ui/src/lib/utils.ts` |
| `TAILWIND` | `agent-evals/src/agent_evals/observatory/web/ui/tailwind.config.ts` |
| `PACKAGE` | `agent-evals/src/agent_evals/observatory/web/ui/package.json` |
| `ROUTES` | `agent-evals/src/agent_evals/observatory/web/routes.py` |
| `MODEL_CLI` | `agent-evals/src/agent_evals/observatory/model_cli.py` |
| `MODEL_CATALOG` | `agent-evals/src/agent_evals/observatory/model_catalog.py` |
| `ROUTES_TEST` | `agent-evals/tests/test_model_browser_web.py` |
| `UI_DIR` | `agent-evals/src/agent_evals/observatory/web/ui` |

---

## Phase 1: Bug Fixes

### Task 1: Fix Invalid Date in History Tab

The `first_seen` and `last_seen` fields are ISO 8601 strings from the DB (via `_now_iso()`), but the frontend multiplies them by 1000 as if they were Unix timestamps. The `created` field IS a Unix timestamp.

**Files:**
- Modify: `MODELS_PAGE` lines 580-592 (History tab content)
- Modify: `MODELS_TEST` (update mock data to use ISO strings for first_seen/last_seen)

**Step 1: Update test mock data to match actual DB format**

In `MODELS_TEST`, the `mockModels` array (line 42-68) uses numbers for `first_seen`/`last_seen`. Update to ISO strings to match real data:

```typescript
// Change from:
first_seen: 1700000000,
last_seen: 1700100000,
// Change to:
first_seen: "2023-11-14T22:13:20Z",
last_seen: "2023-11-15T25:00:00Z",
```

**Step 2: Write failing test for History tab dates**

Add to `MODELS_TEST`:

```typescript
describe("Models page — History tab dates (Bug Fix)", () => {
  it("should display first_seen and last_seen as valid dates", () => {
    vi.mocked(useModelDetail).mockReturnValue({
      data: {
        ...mockModels[0],
        supported_params: [],
        first_seen: "2023-11-14T22:13:20Z",
        last_seen: "2023-11-15T10:00:00Z",
      },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useModelDetail>);

    render(<Models />, { wrapper: createWrapper() });
    // Open panel
    fireEvent.click(screen.getByText("GPT-4o"));
    // Switch to History tab
    fireEvent.click(screen.getByText("History"));
    // Should NOT show "Invalid Date"
    expect(screen.queryByText("Invalid Date")).not.toBeInTheDocument();
  });
});
```

**Step 3: Run test to verify it fails**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

Expected: FAIL — "Invalid Date" is still rendered.

**Step 4: Fix the History tab date rendering in Models.tsx**

In `MODELS_PAGE`, replace the History tab content (lines 580-602):

```typescript
{panelTab === "history" && modelDetail && (
  <div className="space-y-sp-4">
    <div className="flex justify-between text-body-sm">
      <span className="text-brand-slate">First Seen</span>
      <span className="text-brand-charcoal">
        {new Date(modelDetail.first_seen).toLocaleDateString()}
      </span>
    </div>
    <div className="flex justify-between text-body-sm">
      <span className="text-brand-slate">Last Seen</span>
      <span className="text-brand-charcoal">
        {new Date(modelDetail.last_seen).toLocaleDateString()}
      </span>
    </div>
    {modelDetail.created > 0 && (
      <div className="flex justify-between text-body-sm">
        <span className="text-brand-slate">Created</span>
        <span className="text-brand-charcoal">
          {formatDeployed(modelDetail.created)}
        </span>
      </div>
    )}
    <div className="flex justify-between text-body-sm">
      <span className="text-brand-slate">Deprecation</span>
      <StatusBadge
        status={modelDetail.removed_at ? "error" : "success"}
        label={modelDetail.removed_at ? "Deprecated" : "Active"}
      />
    </div>
  </div>
)}
```

Key changes:
- `new Date(modelDetail.first_seen)` instead of `new Date(modelDetail.first_seen * 1000)` — ISO strings parse directly
- Same for `last_seen`
- Added `Created` date row using `formatDeployed()` (Unix timestamp, already correct)

**Step 5: Run tests to verify they pass**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

Expected: ALL PASS

**Step 6: Also update the Model type in client.ts**

In `API_CLIENT`, update the `Model` interface to accurately reflect that `first_seen` and `last_seen` are strings:

```typescript
export interface Model {
  id: string;
  name: string;
  context_length: number;
  prompt_price: number;
  completion_price: number;
  modality: string;
  tokenizer: string;
  created: number;
  first_seen: string;   // ISO 8601 string (was: number)
  last_seen: string;     // ISO 8601 string (was: number)
  removed_at: string | null;  // ISO 8601 string | null (was: number | null)
}
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts
git commit -m "fix(models): fix Invalid Date in History tab by parsing ISO strings correctly"
```

---

### Task 2: Add Provider Endpoints Backend Route

The frontend calls `GET /api/models/{id}/endpoints` but the route doesn't exist. The logic already exists in `model_cli.py:fetch_provider_endpoints()`.

**Files:**
- Modify: `ROUTES` (add new route after line 368)
- Modify: `ROUTES_TEST` (add test for new route)

**Step 1: Write failing backend test**

Add to `ROUTES_TEST`:

```python
def test_model_endpoints_route_returns_200(client, mock_catalog):
    """GET /api/models/{id}/endpoints should return provider data."""
    mock_catalog.get_model.return_value = {
        "id": "anthropic/claude-sonnet-4",
        "name": "Claude Sonnet 4",
    }
    resp = client.get("/api/models/anthropic/claude-sonnet-4/endpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert "endpoints" in data
```

**Step 2: Run test to verify it fails**

```bash
cd agent-evals && uv run pytest tests/test_model_browser_web.py::test_model_endpoints_route_returns_200 -v
```

Expected: FAIL — 404 Not Found

**Step 3: Add the route in routes.py**

Add after the `get_model` route (after line 368 in `ROUTES`):

```python
@router.get("/api/models/{model_id:path}/endpoints")
async def get_model_endpoints(model_id: str) -> dict[str, Any]:
    """Proxy provider endpoint data from OpenRouter."""
    try:
        import httpx

        parts = model_id.split("/", 1)
        if len(parts) < 2:
            return {"endpoints": []}
        resp = httpx.get(
            f"https://openrouter.ai/api/v1/models/{model_id}/endpoints",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Normalize to our ProviderEndpoint shape
            raw_endpoints = data.get("data", {}).get("endpoints", [])
            endpoints = []
            for ep in raw_endpoints:
                endpoints.append({
                    "provider": ep.get("provider_name", ep.get("name", "Unknown")),
                    "latency_ms": ep.get("latency_ms", 0),
                    "uptime_pct": ep.get("uptime", 0) * 100 if ep.get("uptime", 0) <= 1 else ep.get("uptime", 0),
                    "pricing_diff": 0,
                    "quantization": ep.get("quantization", ""),
                    "supported_params": [],
                    "zero_downtime_routing": ep.get("is_zdr", False),
                })
            return {"endpoints": endpoints}
        return {"endpoints": []}
    except Exception:
        return {"endpoints": []}
```

**Important:** This route MUST be defined BEFORE the `GET /api/models/{model_id:path}` catch-all route, otherwise FastAPI will match `anthropic/claude-sonnet-4/endpoints` as a model_id. Move it to between the sync routes and the get_model route.

**Step 4: Run test to verify it passes**

```bash
cd agent-evals && uv run pytest tests/test_model_browser_web.py -v -k "endpoint"
```

Expected: PASS (note: the test may need mocking of httpx.get — adjust accordingly)

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/routes.py agent-evals/tests/test_model_browser_web.py
git commit -m "feat(models): add /api/models/{id}/endpoints route proxying to OpenRouter"
```

---

### Task 3: Fix Card View Toggle

The card view toggle button updates state correctly but the card grid may not render. Debug and fix.

**Files:**
- Modify: `MODELS_PAGE` (card view section, lines 436-448)
- Modify: `MODELS_TEST`

**Step 1: Write a test that verifies card view renders cards**

Add to `MODELS_TEST`:

```typescript
describe("Models page — Card view (Bug Fix)", () => {
  it("should render model cards in card view mode", () => {
    render(<Models />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText(/card view/i));
    // In card view, models render inside Card components (no table)
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    // Model names should still be visible
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    expect(screen.getByText("Claude Sonnet 4")).toBeInTheDocument();
  });
});
```

**Step 2: Run test to see current state**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx -t "Card view" --reporter=verbose
```

**Step 3: Debug and fix**

Likely issues:
- The `ModelCard` onClick opens the detail panel but doesn't toggle selection — this is correct by design
- Check if the card grid is hidden behind the sidebar layout (`flex gap-sp-6` parent)
- Check if there's a CSS overflow issue clipping the card grid

Fix the card grid to ensure it renders visible cards. Also ensure the `ModelCard` component renders both the model name and key data (price, context, modality).

**Step 4: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "fix(models): fix card view toggle not rendering card grid"
```

---

### Task 4: Fix Tokenizer Column Empty Values

**Files:**
- Modify: `MODELS_PAGE` (columns definition, line 261)

**Step 1: Update the tokenizer column to show em-dash for empty values**

In `MODELS_PAGE`, change line 261 from:

```typescript
{ accessorKey: "tokenizer", header: "Tokenizer" },
```

To:

```typescript
{
  accessorKey: "tokenizer",
  header: "Tokenizer",
  cell: ({ getValue }) => getValue<string>() || "\u2014",
},
```

**Step 2: Run existing tests to verify no breakage**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 3: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx
git commit -m "fix(models): show em-dash for empty tokenizer values"
```

---

## Phase 2: Core Features

### Task 5: Add Virtual Scrolling to DataTable

**Files:**
- Modify: `PACKAGE` (add dependency)
- Modify: `DATA_TABLE` (wrap tbody with virtualizer)
- Modify: `DATA_TABLE_TEST`

**Step 1: Install @tanstack/react-virtual**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && pnpm add @tanstack/react-virtual
```

**Step 2: Write test for virtual scrolling behavior**

Add to `DATA_TABLE_TEST`:

```typescript
it("should render a scrollable container for large datasets", () => {
  const manyRows = Array.from({ length: 100 }, (_, i) => ({
    id: `row-${i}`,
    name: `Item ${i}`,
  }));
  const cols: ColumnDef<{ id: string; name: string }>[] = [
    { accessorKey: "name", header: "Name" },
  ];
  const { container } = render(
    <DataTable columns={cols} data={manyRows} />
  );
  // Should have a scrollable container with fixed height
  const scrollContainer = container.querySelector("[data-virtual-scroller]");
  expect(scrollContainer).toBeInTheDocument();
});
```

**Step 3: Run test to verify it fails**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/components/DataTable.test.tsx -t "scrollable" --reporter=verbose
```

**Step 4: Implement virtual scrolling**

Modify `DATA_TABLE` to use `@tanstack/react-virtual`:

```typescript
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
```

Replace the `<tbody>` section (lines 78-118) with:

```typescript
<tbody>
  {(() => {
    const rows = table.getRowModel().rows;
    if (rows.length <= 50) {
      // Small dataset: render normally (no virtualization overhead)
      return rows.map((row) => <RowComponent key={row.id} row={row} />);
    }
    // Large dataset: virtualize
    return (
      <VirtualizedRows
        rows={rows}
        selectedRowIds={selectedRowIds}
        getRowId={getRowId}
        onRowClick={onRowClick}
      />
    );
  })()}
</tbody>
```

Create a `VirtualizedRows` helper that:
1. Uses `useVirtualizer` with `count: rows.length`, `estimateSize: () => 48`
2. Renders only visible rows with absolute positioning
3. Wraps in a `<tr>` with `data-virtual-scroller` attribute for testing

**Step 5: Run all DataTable tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/components/DataTable.test.tsx --reporter=verbose
```

**Step 6: Run full test suite to verify no breakage**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/package.json \
       agent-evals/src/agent_evals/observatory/web/ui/pnpm-lock.yaml \
       agent-evals/src/agent_evals/observatory/web/ui/src/components/DataTable.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/components/DataTable.test.tsx
git commit -m "feat(models): add virtual scrolling for large model lists"
```

---

### Task 6: Add Select-All Checkbox

**Files:**
- Modify: `DATA_TABLE` (add header checkbox)
- Modify: `MODELS_PAGE` (pass onSelectAll callback)
- Modify: `MODELS_TEST`

**Step 1: Write failing test**

Add to `MODELS_TEST`:

```typescript
describe("Models page — Select All", () => {
  it("should render a select-all checkbox in the table header", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByLabelText(/select all/i)).toBeInTheDocument();
  });

  it("should select all models when select-all is clicked", () => {
    render(<Models />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText(/select all/i));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("should deselect all when select-all is clicked again", () => {
    render(<Models />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText(/select all/i));
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/select all/i));
    expect(screen.queryByText("2 selected")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run to verify it fails**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx -t "Select All" --reporter=verbose
```

**Step 3: Implement**

Add `onSelectAll?: (allIds: string[]) => void` prop to `DataTableProps`. In the header row, add a checkbox cell:

```typescript
{selectedRowIds && (
  <th className="w-10 px-sp-2">
    <CompassCheckbox
      checked={selectedRowIds.size > 0 && selectedRowIds.size === data.length}
      aria-label="Select all"
      onCheckedChange={(checked) => {
        if (checked && getRowId) {
          onSelectAll?.(data.map(getRowId));
        } else {
          onSelectAll?.([]);
        }
      }}
    />
  </th>
)}
```

In `MODELS_PAGE`, add the `onSelectAll` handler:

```typescript
const handleSelectAll = (ids: string[]) => {
  if (ids.length === 0) {
    setSelectedModelIds(new Set());
  } else {
    setSelectedModelIds(new Set(ids));
  }
};
```

Pass it to `<DataTable onSelectAll={handleSelectAll} ... />`.

Also, always show checkboxes for each row (not just when selected). Update the tbody cell:

```typescript
{selectedRowIds && (
  <td className="px-sp-2 py-sp-3 w-10">
    <CompassCheckbox
      checked={isSelected}
      aria-label={`Select row`}
    />
  </td>
)}
```

**Step 4: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/DataTable.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "feat(models): add select-all checkbox to model table"
```

---

### Task 7: Search Improvements (Debounce + Keyboard Shortcut)

**Files:**
- Modify: `MODELS_PAGE` (add debounce, keyboard shortcut, search in toolbar)
- Modify: `MODELS_TEST`

**Step 1: Write failing tests**

```typescript
describe("Models page — Search improvements", () => {
  it("should focus search on '/' key press", () => {
    render(<Models />, { wrapper: createWrapper() });
    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.keyDown(document, { key: "/" });
    expect(document.activeElement).toBe(searchInput);
  });
});
```

**Step 2: Run to verify it fails**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx -t "Search improvements" --reporter=verbose
```

**Step 3: Implement**

Add a ref to the search Input and a keyboard listener:

```typescript
const searchRef = useRef<HTMLInputElement>(null);

useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
      e.preventDefault();
      searchRef.current?.focus();
    }
    if (e.key === "Escape") {
      clearSelection();
    }
  };
  document.addEventListener("keydown", handleKeyDown);
  return () => document.removeEventListener("keydown", handleKeyDown);
}, [clearSelection]);
```

Add ref to the Input: `<Input ref={searchRef} ... />`

For debounce, add a local `searchTerm` state with a 300ms `useEffect` that calls `setFilters`:

```typescript
const [searchTerm, setSearchTerm] = useState(filters.search ?? "");

useEffect(() => {
  const timer = setTimeout(() => {
    setFilters({ search: searchTerm || undefined });
  }, 300);
  return () => clearTimeout(timer);
}, [searchTerm, setFilters]);
```

**Step 4: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "feat(models): add search debounce and '/' keyboard shortcut"
```

---

### Task 8: Reset Filters Button

**Files:**
- Modify: `MODELS_PAGE`
- Modify: `MODELS_TEST`

**Step 1: Write failing test**

```typescript
describe("Models page — Reset filters", () => {
  it("should show 'Clear all' when filters are active", () => {
    vi.mocked(useFilterParams).mockReturnValue([
      { free: true },
      mockSetFilters,
    ]);
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText(/clear all/i)).toBeInTheDocument();
  });

  it("should not show 'Clear all' when no filters active", () => {
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.queryByText(/clear all/i)).not.toBeInTheDocument();
  });
});
```

**Step 2: Run to verify it fails**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx -t "Reset filters" --reporter=verbose
```

**Step 3: Implement**

Add a helper to detect active filters:

```typescript
const hasActiveFilters = Boolean(
  filters.search || filters.free || filters.maxPrice != null ||
  filters.minContext != null || filters.modality
);
```

Below the model count, add:

```typescript
<p className="text-caption text-brand-slate mt-sp-4">
  {total} models found
  {hasActiveFilters && (
    <button
      className="ml-sp-2 text-brand-goldenrod hover:underline"
      onClick={() => {
        setFilters({
          search: undefined, free: undefined, maxPrice: undefined,
          minContext: undefined, modality: undefined,
        });
        setSearchTerm("");
      }}
    >
      Clear all
    </button>
  )}
</p>
```

**Step 4: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/Models.test.tsx --reporter=verbose
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "feat(models): add 'Clear all' reset filters button"
```

---

## Phase 3: Visual Polish

### Task 9: Table Visual Improvements

Alternating rows, right-aligned numeric columns, always-visible checkboxes, better hover states.

**Files:**
- Modify: `DATA_TABLE` (row styling, cell alignment)
- Modify: `MODELS_PAGE` (column definitions with alignment)

**Step 1: Update DataTable row styling**

In `DATA_TABLE`, add alternating row backgrounds. Change the `<tr>` className (line 86):

```typescript
className={cn(
  "border-t border-brand-mist transition-colors duration-micro",
  "hover:bg-brand-cream/50",
  rowIndex % 2 === 0 ? "bg-white" : "bg-brand-cream/20",
  onRowClick && "cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
  isSelected && "bg-brand-goldenrod/10",
)}
```

Add `rowIndex` from the `.map()` callback.

**Step 2: Right-align numeric columns in Models.tsx**

Update the column definitions to include `meta` for alignment:

```typescript
{
  accessorKey: "prompt_price",
  header: () => (
    <Tooltip content="Cost per million prompt (input) tokens">
      <span className="cursor-help">Prompt $/M</span>
    </Tooltip>
  ),
  cell: ({ getValue }) => formatPrice(getValue<number>()),
  meta: { align: "right" },
},
```

In `DATA_TABLE`, use the column meta for alignment:

```typescript
<td
  key={cell.id}
  className={cn(
    "px-sp-4 py-sp-3 text-brand-charcoal",
    (cell.column.columnDef.meta as { align?: string })?.align === "right" && "text-right tabular-nums",
  )}
>
```

Apply `meta: { align: "right" }` to: `prompt_price`, `completion_price`, `context_length`, `created` columns.

**Step 3: Run all tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/DataTable.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx
git commit -m "feat(models): add alternating rows and right-aligned numeric columns"
```

---

### Task 10: Improved Card View

Richer model cards with provider badge, price range, context-length bar, and capability tags.

**Files:**
- Modify: `MODELS_PAGE` (ModelCard component, lines 145-174)

**Step 1: Rewrite ModelCard with richer content**

```typescript
function ModelCard({
  model,
  onClick,
  maxContext,
}: {
  model: Model;
  onClick: () => void;
  maxContext: number;
}) {
  const provider = model.id.split("/")[0];
  const contextPct = maxContext > 0 ? (model.context_length / maxContext) * 100 : 0;

  return (
    <Card variant="interactive" onClick={onClick}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="truncate">{model.name}</CardTitle>
          <CopyModelIdButton modelId={model.id} />
        </div>
        <span className="text-caption text-brand-slate capitalize">{provider}</span>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-sp-2 mb-sp-3">
          <StatusBadge
            status={model.prompt_price === 0 ? "new" : "neutral"}
            label={model.prompt_price === 0 ? "Free" : `${formatPrice(model.prompt_price)} in`}
          />
          {model.completion_price > 0 && (
            <StatusBadge status="neutral" label={`${formatPrice(model.completion_price)} out`} />
          )}
          <StatusBadge status="neutral" label={model.modality} />
        </div>
        {/* Context length bar */}
        <div className="mt-sp-3">
          <div className="flex justify-between text-caption text-brand-slate mb-sp-1">
            <span>Context</span>
            <span>{(model.context_length / 1000).toFixed(0)}k</span>
          </div>
          <div className="h-1.5 bg-brand-mist rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-goldenrod rounded-full transition-all duration-state"
              style={{ width: `${Math.max(contextPct, 2)}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

**Step 2: Update card grid render to pass maxContext**

```typescript
{viewMode === "cards" && (
  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-sp-4">
    {(() => {
      const maxCtx = Math.max(...models.map((m) => m.context_length), 1);
      return models.map((model) => (
        <ModelCard
          key={model.id}
          model={model}
          maxContext={maxCtx}
          onClick={() => {
            setSelectedModelId(model.id);
            setPanelTab("overview");
          }}
        />
      ));
    })()}
  </div>
)}
```

**Step 3: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx
git commit -m "feat(models): improve card view with provider badge and context bar"
```

---

### Task 11: Slide-Out Panel Polish

Sticky header, copy button in header, created date, total cost estimate.

**Files:**
- Modify: `MODELS_PAGE` (panel content)
- Modify: `SLIDE_OUT` (sticky header)

**Step 1: Add sticky header to SlideOutPanel**

In `SLIDE_OUT`, make the title/close button area sticky:

```typescript
<div className="sticky top-0 z-10 bg-white border-b border-brand-mist px-sp-6 py-sp-4 flex items-center justify-between">
```

**Step 2: Add total cost estimate to pricing cards**

In the Overview tab pricing section of `MODELS_PAGE`, after the two price cards, add:

```typescript
<p className="text-caption text-brand-slate text-center mt-sp-2">
  ~${((modelDetail.prompt_price + modelDetail.completion_price) * 1_000_000).toFixed(2)}/M tokens (in + out)
</p>
```

**Step 3: Add "Created" date to Overview tab**

After the Status row in the Overview info grid:

```typescript
{modelDetail.created > 0 && (
  <div className="flex justify-between text-body-sm">
    <span className="text-brand-slate">Created</span>
    <span className="text-brand-charcoal font-medium">
      {formatDeployed(modelDetail.created)}
    </span>
  </div>
)}
```

**Step 4: Add provider count badge to Providers tab**

Update the TabBar tabs array:

```typescript
{ key: "providers", label: `Providers${endpoints.length > 0 ? ` (${endpoints.length})` : ""}` },
```

**Step 5: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 6: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx
git commit -m "feat(models): polish slide-out panel with sticky header, cost estimate, dates"
```

---

### Task 12: Collapsible Filter Sections

**Files:**
- Modify: `FILTER_PANEL` (make FilterSection collapsible)
- Modify: `FILTER_PANEL_TEST` (if exists, otherwise add tests)

**Step 1: Make FilterSection collapsible**

Add state to FilterSection:

```typescript
export function FilterSection({ label, children, defaultOpen = true }: FilterSectionProps & { defaultOpen?: boolean }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="mb-sp-6">
      <button
        className="flex items-center justify-between w-full mb-sp-3 text-body-sm font-medium text-brand-charcoal hover:text-brand-goldenrod transition-colors duration-micro"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        {label}
        <ChevronDown className={cn(
          "h-4 w-4 transition-transform duration-micro",
          isOpen && "rotate-180"
        )} />
      </button>
      {isOpen && children}
    </div>
  );
}
```

Import `ChevronDown` from lucide-react and `useState` from react.

**Step 2: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 3: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/FilterPanel.tsx
git commit -m "feat(models): make filter sections collapsible"
```

---

### Task 13: Empty State for No Results

**Files:**
- Modify: `MODELS_PAGE`
- Modify: `MODELS_TEST`

**Step 1: Write failing test**

```typescript
describe("Models page — Empty state", () => {
  it("should show empty state when no models match filters", () => {
    vi.mocked(useModels).mockReturnValue({
      data: { models: [], total: 0 },
      isLoading: false,
      error: null,
    } as ReturnType<typeof useModels>);
    vi.mocked(useFilterParams).mockReturnValue([
      { free: true },
      mockSetFilters,
    ]);
    render(<Models />, { wrapper: createWrapper() });
    expect(screen.getByText(/no models match/i)).toBeInTheDocument();
  });
});
```

**Step 2: Implement empty state**

After the table/card grid conditional, add:

```typescript
{models.length === 0 && !isLoading && (
  <div className="text-center py-sp-16">
    <Cpu className="h-12 w-12 text-brand-mist mx-auto mb-sp-4" />
    <p className="text-h5 text-brand-charcoal mb-sp-2">No models match your filters</p>
    <p className="text-body-sm text-brand-slate mb-sp-6">
      Try adjusting your search or filter criteria.
    </p>
    {hasActiveFilters && (
      <Button
        variant="secondary"
        onClick={() => {
          setFilters({
            search: undefined, free: undefined, maxPrice: undefined,
            minContext: undefined, modality: undefined,
          });
          setSearchTerm("");
        }}
      >
        Reset all filters
      </Button>
    )}
  </div>
)}
```

**Step 3: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "feat(models): add empty state when no models match filters"
```

---

## Phase 4: Provider Filter + Mobile

### Task 14: Provider/Vendor Filter

**Files:**
- Modify: `MODELS_PAGE` (add provider filter to sidebar)
- Modify: `MODELS_TEST`

**Step 1: Extract providers from model IDs**

Add a helper function:

```typescript
function extractProviders(models: Model[]): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const m of models) {
    const provider = m.id.split("/")[0];
    const display = provider.charAt(0).toUpperCase() + provider.slice(1);
    counts.set(display, (counts.get(display) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}
```

**Step 2: Add provider filter to sidebar**

After the Modality filter section:

```typescript
<FilterSection label="Provider">
  {providers.slice(0, 10).map((p) => (
    <FilterCheckbox
      key={p.name}
      label={`${p.name} (${p.count})`}
      checked={selectedProviders.has(p.name.toLowerCase())}
      onCheckedChange={(checked) => {
        setSelectedProviders((prev) => {
          const next = new Set(prev);
          if (checked) next.add(p.name.toLowerCase());
          else next.delete(p.name.toLowerCase());
          return next;
        });
      }}
    />
  ))}
</FilterSection>
```

Add state: `const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set());`

Filter models client-side before rendering:

```typescript
const filteredModels = selectedProviders.size > 0
  ? models.filter((m) => selectedProviders.has(m.id.split("/")[0]))
  : models;
```

Use `filteredModels` instead of `models` for rendering.

**Step 3: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx \
       agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/Models.test.tsx
git commit -m "feat(models): add provider/vendor filter in sidebar"
```

---

### Task 15: Mobile Responsive Filters

**Files:**
- Modify: `MODELS_PAGE` (add mobile filter button + sheet)

**Step 1: Add mobile filter button**

Wrap the filter sidebar in a shared component and add a mobile toggle:

```typescript
{/* Mobile filter button */}
<div className="lg:hidden mb-sp-4 flex items-center gap-sp-3">
  <Input
    ref={searchRef}
    placeholder="Search models..."
    value={searchTerm}
    onChange={(e) => setSearchTerm(e.target.value)}
    className="flex-1"
  />
  <Button variant="secondary" size="sm" onClick={() => setShowMobileFilters(true)}>
    <Filter className="h-4 w-4 mr-sp-1" />
    Filters
    {hasActiveFilters && (
      <span className="ml-sp-1 bg-brand-goldenrod text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
        !
      </span>
    )}
  </Button>
</div>
```

Add `Filter` import from lucide-react. Add state: `const [showMobileFilters, setShowMobileFilters] = useState(false);`

Use a `SlideOutPanel` for mobile filters:

```typescript
<SlideOutPanel
  open={showMobileFilters}
  onClose={() => setShowMobileFilters(false)}
  title="Filters"
  width="md"
>
  {/* Same filter content as sidebar */}
  <FilterSection label="Pricing">...</FilterSection>
  <FilterSection label="Context Length">...</FilterSection>
  <FilterSection label="Modality">...</FilterSection>
  <FilterSection label="Provider">...</FilterSection>
</SlideOutPanel>
```

Extract the filter content into a `FilterContent` component to avoid duplication.

**Step 2: Run tests**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

**Step 3: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/Models.tsx
git commit -m "feat(models): add mobile responsive filters with slide-out panel"
```

---

## Final Verification

### Task 16: Full Test Suite + Visual Verification

**Step 1: Run full frontend test suite**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run --reporter=verbose
```

All tests must pass.

**Step 2: Run full backend test suite**

```bash
cd agent-evals && uv run pytest -v
```

**Step 3: Visual verification**

Open `http://localhost:5173/models` and verify:
- [ ] Table loads with 336 models, virtual scrolling works
- [ ] Card view toggle switches correctly
- [ ] Click model name → panel opens with valid dates
- [ ] History tab shows correct dates (no "Invalid Date")
- [ ] Providers tab loads data (or shows clean empty state)
- [ ] Select-all checkbox works
- [ ] Search with `/` shortcut works
- [ ] Provider filter in sidebar works
- [ ] Collapsible filter sections work
- [ ] "Clear all" appears when filters active
- [ ] Empty state when no results
- [ ] Cards show provider badge, context bar
- [ ] Numeric columns right-aligned

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore(models): final verification pass for models page overhaul"
```
