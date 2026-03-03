# Models Page Overhaul Design

**Date:** 2026-03-03
**Status:** Approved
**Scope:** Full overhaul of the Observatory Models page - bugs, features, and visual improvements

## Context

The Models page (`/models`) is the OpenRouter model browser in the Observatory UI. It displays 336+ models with filtering, search, table/card views, and a slide-out detail panel. Several bugs and UX gaps were identified through visual inspection and code review.

## Bug Fixes

### 1. Invalid Date in History Tab
- **Root cause:** `first_seen` and `last_seen` are ISO 8601 strings in the DB but the frontend treats them as Unix timestamps (`new Date(val * 1000)`)
- **Fix:** Use `new Date(val)` for ISO strings; keep `* 1000` only for the `created` field (actual Unix timestamp)
- **File:** `Models.tsx` lines 581-592

### 2. Providers Tab - Missing Backend Endpoint
- **Root cause:** Frontend calls `GET /api/models/{id}/endpoints` but the route doesn't exist in the web API. Logic exists only in `model_cli.py`.
- **Fix:** Add the route in `routes.py` that proxies to OpenRouter's `/api/v1/models/{id}/endpoints`, reusing `model_cli.py` logic
- **Files:** `routes.py` (new route), possibly `model_catalog.py` (cache layer)

### 3. Card View Toggle Not Rendering
- **Root cause:** State toggle logic is correct but cards may not render due to layout/visibility issue
- **Fix:** Debug and fix the card grid rendering

### 4. Tokenizer Column Mostly Empty
- **Fix:** Show em-dash for empty values; consider hiding column by default

## Functional Improvements

### 5. Virtual Scrolling
- Add `@tanstack/react-virtual` to virtualize the table body
- Render ~30 visible rows with smooth scroll
- Handles 336+ models without DOM performance issues

### 6. Sort Controls
- Clickable column headers with ascending/descending indicators
- Uses existing `sort` API parameter
- Default: `created` descending (newest first)

### 7. Provider/Vendor Filter
- Extract provider prefix from model IDs (e.g., `anthropic/claude-sonnet-4.6` -> "Anthropic")
- Multi-select dropdown in the sidebar with top providers and counts
- Frontend-side filtering (API doesn't support provider filter natively)

### 8. Search Improvements
- Search accessible in toolbar area (not just sidebar) for all screen sizes
- Keyboard shortcut: `/` to focus search
- 300ms debounce on search input

### 9. Mobile Responsive Filters
- "Filters" button on mobile opens sidebar as slide-over sheet
- Currently `hidden lg:block` with no mobile fallback

### 10. Select-All Checkbox
- Checkbox in table header for select-all visible models
- Updates selection count and bulk action buttons

### 11. Reset Filters Button
- "Clear all" link next to model count when any filter is active

## Visual Improvements

### 12. Table Density & Readability
- Alternating row backgrounds (`bg-brand-cream/30` on even rows)
- Hover highlight on rows
- Right-align numeric columns (prices, context length)
- Visible checkbox column on the left for row selection

### 13. Improved Card View
- Cards show: model name, provider badge, price range, context-length bar, modality icon, capabilities preview (first 3-4 tags)
- Visual context-length bar proportional to max in dataset

### 14. Slide-Out Panel Polish
- Sticky model name header
- "Copy model ID" button in panel header
- Total cost estimate in pricing cards
- Show "Created" date in Overview tab
- Provider count badge on Providers tab label

### 15. Filter Sidebar Polish
- Collapsible filter sections
- Active filter indicators (dot/count) on collapsed sections
- Auto-scale price slider max based on actual data range

### 16. Empty States
- "No results" state with illustration and reset button
- Loading skeletons that match actual table layout

## Implementation Plan

### Phase 1: Bug Fixes (items 1-4)
Smallest blast radius, unblocks other work.

### Phase 2: Core Features (items 5-8, 10-11)
Virtual scrolling, sort, search, select-all, reset filters.

### Phase 3: Visual Polish (items 12-16)
Table styling, card view, panel, sidebar, empty states.

### Phase 4: Provider Endpoint + Mobile (items 2-backend, 7, 9)
Backend route, provider filter, mobile responsive filters.

## Dependencies
- `@tanstack/react-virtual` (new package)
- OpenRouter API access for provider endpoints proxy
