# Observatory Dashboard - UX Polish Audit

**Auditor:** ux-auditor agent
**Date:** 2026-02-24
**Scope:** All pages and components in `agent-evals/src/agent_evals/observatory/web/ui/src/`

---

## Executive Summary

The Observatory Dashboard has solid bones: a well-defined brand palette (goldenrod, charcoal, cream), Playfair Display + Inter typography pairing, good accessibility foundations (focus rings, reduced-motion, ARIA), and the CompassCheckbox draw-in animation sets a high bar. However, the dashboard currently feels like **a well-themed template** rather than a **premium product**. The gap is in micro-interactions, loading states, empty states, visual depth, and the connective tissue between states that makes dashboards like Linear and Vercel feel *alive*.

Below are prioritized recommendations organized by effort-to-impact ratio.

---

## HIGH IMPACT / LOW-MEDIUM EFFORT

### 1. Loading States Are Bare Text — Add Skeleton Screens

**Current:** Every page uses `<p className="text-body text-brand-slate">Loading...</p>` — flat, lifeless text.

**Problem:** This is the most jarring anti-pattern in the dashboard. Every page transition shows "Loading..." which feels broken, not premium.

**Recommendation:** Create a `<Skeleton />` component with a branded shimmer animation using goldenrod-to-cream gradient sweep.

**Files to create/modify:**
- NEW: `src/components/Skeleton.tsx`
- Modify: `Observatory.tsx:140-142`, `LiveMonitor.tsx:125-131`, `ResultsExplorer.tsx:174-176`, `History.tsx:122-128`, `Models.tsx:253-259`, `FactorAnalysis.tsx:86-92`

```
+--------------------------------------------------+
|  ████████████████████░░░░░░ (shimmer sweeping →)  |
|  ████████████░░░░░░░░░░                           |
|  ████████████████████████████░░░░░                 |
+--------------------------------------------------+
```

**Skeleton shimmer keyframe (add to globals.css):**
```css
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.skeleton {
  background: linear-gradient(90deg, #E5E5E5 25%, #F7F5F0 50%, #E5E5E5 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: 8px;
}
```

**Priority: HIGHEST** — This single change will make the entire app feel 2x more polished.

---

### 2. Stat Cards Need Animated Number Counters

**Current:** Numbers like "$4.52" and "12,450" appear instantly — no animation.

**Problem:** Static numbers feel dead. When data loads, the numbers should *arrive*, not just appear. Think Stripe dashboard where revenue numbers count up smoothly.

**Recommendation:** Create an `<AnimatedNumber />` component that counts from 0 to the target value with an ease-out curve over ~600ms.

**Files to modify:**
- NEW: `src/components/AnimatedNumber.tsx`
- `Observatory.tsx:153-155` (Total Spend), `:163-164` (Total Tokens), `:173-174` (Cost/Trial)
- `LiveMonitor.tsx:298-299` (StatCard value)
- `ResultsExplorer.tsx:218-220` (Total Trials), `:228-229` (Mean Score), `:238-239` (Total Cost)

**Implementation sketch:**
```tsx
function AnimatedNumber({ value, format, duration = 600 }) {
  // Use requestAnimationFrame to interpolate from 0 → value
  // Apply ease-out cubic: t * (2 - t)
  // Format with the provided formatter at each frame
}
```

**Priority: HIGH** — Small component, huge perceived quality improvement.

---

### 3. Nav Bar Needs Brand Personality

**Current:** (`App.tsx:34-58`) The nav is a plain white bar with text links. The "Observatory" title is Playfair Display but has no distinctive mark. Hover states are plain background color changes.

**Problem:** The nav is the single most-seen element and it's the most generic part of the dashboard. Zero brand distinctiveness.

**Recommendations:**
- **Add a compass icon/logo** next to "Observatory" — even a simple SVG compass rose in goldenrod would add immense brand character
- **Active nav indicator:** Replace the simple background highlight with an **animated underline** that slides to the active item (like Vercel's tab bar). Use a `motion` div with `layoutId` or a CSS approach with `transform: translateX()` calculated from the active item position
- **Add a subtle bottom border glow** on the active item using `box-shadow: 0 2px 0 0 var(--color-action)` instead of just background opacity
- **Sticky nav with backdrop blur:** Add `sticky top-0 z-50 backdrop-blur-md bg-brand-bone/90` so the nav stays visible on scroll with a frosted glass effect

**File:** `App.tsx:33-58`

**Priority: HIGH** — The nav is constant across all pages; polish here pays dividends everywhere.

---

### 4. Empty States Are Boring — Make Them Engaging and Actionable

**Current empty states (all just text):**
- `LiveMonitor.tsx:140-143`: "No active runs. Start an evaluation to see live results."
- `ResultsExplorer.tsx:168-172`: "Select a run to view results."
- `PipelineView.tsx:82-88`: "No pipelines yet. Run an evaluation with `--pipeline auto` to create one."
- `LiveMonitor.tsx:217-219`: "Waiting for trial results..."
- `History.tsx:152-154`: "No completed runs yet."

**Problem:** These are missed opportunities. Empty states are the first thing new users see. They should be delightful and guide action.

**Recommendation:** Create an `<EmptyState />` component with:
- A branded illustration (compass rose SVG or abstract geometric pattern using brand colors)
- A heading + description
- A primary CTA button where appropriate
- A subtle fade-in animation

```
+--------------------------------------------------+
|                                                    |
|              ◇ (compass rose, goldenrod)           |
|                                                    |
|           No pipelines yet                         |
|    Run an evaluation with --pipeline auto           |
|    to create your first pipeline.                  |
|                                                    |
|         [ Start Evaluation →  ]                    |
|                                                    |
+--------------------------------------------------+
```

**File:** NEW `src/components/EmptyState.tsx`, then update all 5+ empty state locations.

**Priority: HIGH** — First impressions matter. New users will see these before anything else.

---

### 5. Page Transitions Are Abrupt — Add Route-Level Animation

**Current:** FadeIn components handle initial element animation well, but switching between routes (e.g., Run Config → Live Monitor) has no transition. The page just swaps.

**Problem:** Route changes feel jarring — one page vanishes, another appears. Premium dashboards have smooth crossfades.

**Recommendation:** Wrap `<Routes>` in a simple crossfade using CSS transitions on route change. Use `React.Suspense` + `startTransition` for a React 18 approach, or add `framer-motion`'s `AnimatePresence` around Routes.

Simpler CSS-only approach: wrap `<main>` content in the FadeIn component and key it on `location.pathname`:

```tsx
// App.tsx — wrap Routes with animated transition
const location = useLocation();
<main key={location.pathname}>
  <div className="animate-fade-in-up" style={{ animationDuration: '200ms' }}>
    <Routes location={location}>...</Routes>
  </div>
</main>
```

**File:** `App.tsx:60-85`

**Priority: HIGH** — Small change, big feel improvement.

---

### 6. The ScrollThread Component Is Unused — Wire It Up

**Current:** `ScrollThread.tsx` exists as a beautiful brand detail — a thin goldenrod progress line on the left edge of the viewport. But it's not imported or used anywhere.

**Problem:** Someone built this brand-unique detail and it's sitting unused!

**Recommendation:** Import and add `<ScrollThread />` to `App.tsx` inside the root div. This is a 2-line change.

```tsx
// App.tsx
import { ScrollThread } from "./components/ScrollThread";
// Inside return:
<div className="min-h-screen bg-brand-cream">
  <ScrollThread />
  <nav>...</nav>
  ...
</div>
```

**File:** `App.tsx:1, 33`

**Priority: HIGHEST** — Literally 2 lines of code for a unique brand detail.

---

## MEDIUM IMPACT / MEDIUM EFFORT

### 7. DataTable Needs More Interactive Polish

**Current:** (`DataTable.tsx`) Rows have hover background, selected rows show goldenrod tint + CompassCheckbox. Sorting has a static up/down icon.

**Gaps:**
- **No sort direction indicator:** The `ArrowUpDown` icon never changes. When sorted ascending, it should show `ArrowUp`; descending → `ArrowDown`. Currently always shows the neutral icon.
- **No row entrance animation:** When data loads, rows just appear. Add staggered fade-in per row (50ms delay per row, cap at 500ms).
- **Missing hover row highlight bar:** Add a left-edge goldenrod accent bar on hover (2px wide, transitions in).
- **Checkbox column always shows blank for unselected:** The checkbox column is empty when not selected. Show an unchecked circle outline always (using CompassCheckbox with `checked={false}`) so users know rows are selectable.

**File:** `DataTable.tsx:72-109`

**Specific code change for sort indicator:**
```tsx
// DataTable.tsx:62-63 — Replace static icon with dynamic
{header.column.getIsSorted() === "asc" ? (
  <ArrowUp className="h-4 w-4 text-brand-goldenrod" />
) : header.column.getIsSorted() === "desc" ? (
  <ArrowDown className="h-4 w-4 text-brand-goldenrod" />
) : (
  <ArrowUpDown className="h-4 w-4 text-brand-slate/50" />
)}
```

**Priority: MEDIUM** — Tables are used on History, Results, Models, FactorAnalysis pages.

---

### 8. Cards Need Depth Differentiation and Hover Feedback

**Current:** (`Card.tsx`) Cards have `shadow-card` → `shadow-card-hover` on hover.

**Gaps:**
- **Stat cards (Observatory, LiveMonitor, ResultsExplorer)** should have a subtle left border accent in goldenrod to differentiate them from content cards
- **Clickable cards (PipelineView, Models card view)** need a more obvious hover state: `transform: translateY(-2px)` + the shadow change, plus a ring on focus
- **Non-clickable cards** (data displays) should NOT have hover:shadow-card-hover — it implies interactivity that doesn't exist. The universal hover effect is misleading.

**Recommendation:** Add Card variants:

```tsx
// Card.tsx — add variant prop
variant: "default" | "interactive" | "stat"
// default: no hover effect
// interactive: translateY + shadow + ring
// stat: left goldenrod border accent
```

**Files:** `Card.tsx`, then update all Card usages to specify variant.

**Priority: MEDIUM** — Improves click affordance clarity across all pages.

---

### 9. Select Dropdowns Are Unstyled Native Elements

**Current:** Run selectors on Observatory, ResultsExplorer, PipelineView use raw `<select>` elements with basic Tailwind styling.

**Problem:** Native `<select>` elements are the biggest visual inconsistency. They ignore the brand fonts inside the dropdown menu, have platform-specific appearances, and lack the polish of the rest of the UI.

**Recommendation:** Create a custom `<Select />` component using Radix UI's `@radix-ui/react-select` (already using Radix for Dialog and Checkbox, so it's a natural fit). Style it with brand tokens:

```
+----------------------------------------------+
|  Select a run...                         ▾   |
+----------------------------------------------+
|  taguchi · Feb 23, 10:05 PM · completed     |
|  full · Feb 22, 3:15 PM · active       ◈    |  ← active indicator
|  taguchi · Feb 21, 11:30 AM · completed     |
+----------------------------------------------+
```

**Files:** NEW `src/components/Select.tsx`, update `Observatory.tsx:122-135`, `ResultsExplorer.tsx:148-165`, `PipelineView.tsx:55-72`, `RunConfig.tsx:202-221, 233-250`

**Priority: MEDIUM** — Several pages use native selects; this would unify the feel.

---

### 10. Charts Lack Entry Animation

**Current:** Charts from Chart.js render instantly when data is available.

**Problem:** In premium dashboards (think Vercel Analytics), charts grow/draw in rather than appearing fully formed. Chart.js supports this natively.

**Recommendation:** Add animation config to all chart options objects:

```ts
// Add to all chart options
animation: {
  duration: 800,
  easing: 'easeOutQuart',
},
```

For Line charts, additionally:
```ts
animation: {
  x: { duration: 0 },
  y: { duration: 800, easing: 'easeOutQuart' },
}
```

**Files:** `Observatory.tsx:84-90` (line options), `Observatory.tsx` (doughnut — no explicit options), `LiveMonitor.tsx:112-120`, `ResultsExplorer.tsx:116-123`, `History.tsx:114-120`, `FactorAnalysis.tsx:119-129`

**Priority: MEDIUM** — Easy config change, noticeable improvement.

---

### 11. Progress Bar on LiveMonitor Needs More Life

**Current:** (`LiveMonitor.tsx:163-178`) A simple goldenrod bar filling a gray track.

**Problem:** It works but it's static. For a *live* monitor, it should feel alive.

**Recommendations:**
- Add a **shimmer/pulse gradient** on the progress bar fill that sweeps left-to-right continuously while the run is active (not just the bar growing, but a light sweep within it)
- Add a **percentage label inside the bar** when it's wide enough (>15%), transitioning from outside to inside
- Add subtle **milestone markers** at 25%, 50%, 75% with tick marks on the track

**CSS for shimmer effect:**
```css
@keyframes progress-shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}
/* Apply: */
background: linear-gradient(90deg, #C2A676 0%, #D4A84B 50%, #C2A676 100%);
background-size: 200% 100%;
animation: progress-shimmer 2s linear infinite;
```

**File:** `LiveMonitor.tsx:170-176`

**Priority: MEDIUM** — Live Monitor is high-engagement; this makes it feel premium.

---

### 12. Custom Scrollbar Styling

**Current:** Default browser scrollbars everywhere.

**Problem:** On pages with lots of data (Models table, trial feeds), the default scrollbar breaks the brand immersion.

**Recommendation:** Add branded scrollbar styles in globals.css:

```css
/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: theme("colors.brand.mist");
  border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
  background: theme("colors.brand.slate");
}
```

**File:** `globals.css`

**Priority: MEDIUM** — Affects every scrollable area, subtle but premium.

---

## MEDIUM IMPACT / LOW EFFORT

### 13. Button Press Feedback Needs Refinement

**Current:** (`Button.tsx:17-21`) Primary button has `hover:-translate-y-px` and `active:translate-y-0 active:brightness-95`.

**Gaps:**
- **No haptic-style scale feedback:** Add `active:scale-[0.98]` for a satisfying "press" feel
- **Ghost buttons** have no active state at all — just hover
- **Secondary buttons** also lack active feedback

**Specific change:**
```tsx
// Button.tsx — add to all variants:
primary: "... active:scale-[0.98] active:translate-y-0 active:brightness-95"
secondary: "... active:scale-[0.98] active:bg-brand-mist"
ghost: "... active:scale-[0.98] active:bg-brand-mist"
danger: "... active:scale-[0.98] active:translate-y-0 active:brightness-95"
```

**File:** `Button.tsx:17-32`

**Priority: MEDIUM-LOW** — Quick CSS addition, subtle improvement.

---

### 14. Tab Bars Need Animated Underline Indicator

**Current:** Tab bars on ResultsExplorer (`ResultsExplorer.tsx:182-206`) and Models panel (`Models.tsx:441-457`) use `border-b-2` that snaps between tabs.

**Problem:** The underline jumps from tab to tab. In premium UIs, it *slides*.

**Recommendation:** Use a positioned `<div>` for the indicator that animates its `transform: translateX()` and `width` based on the active tab. Measure tab positions with refs.

Simpler approach (CSS-only): Use a pseudo-element on the active tab with `transition-all duration-state`:

```tsx
// The current implementation already uses border-b-2 on the active button
// Add transition to border:
"transition-all duration-[250ms] ease-in-out"
// This won't slide but will at least fade. For a sliding effect,
// use a separate indicator div positioned absolutely.
```

**File:** `ResultsExplorer.tsx:182-206`, `Models.tsx:441-457`

**Priority: MEDIUM** — Noticeable on interaction-heavy pages.

---

### 15. Tooltip System Is Missing

**Current:** Zero tooltips in the entire dashboard.

**Problem:** Many elements would benefit from tooltips:
- Copy buttons: "Copy model ID" (only has aria-label)
- Table headers with abbreviations: "SS", "df", "MS", "F-ratio", "omega-squared"
- Status badges: explain what "Significant" means
- Stat cards: explain the metric
- Price formats: show raw per-token value

**Recommendation:** Use Radix UI `@radix-ui/react-tooltip` (consistent with existing Radix usage). Create a styled `<Tooltip />` component with brand styling.

**File:** NEW `src/components/Tooltip.tsx`, then sprinkle across:
- `FactorAnalysis.tsx` ANOVA table headers
- `Models.tsx` CopyModelIdButton, price cells
- `LiveMonitor.tsx` stat cards
- `Observatory.tsx` stat cards

**Priority: MEDIUM** — Improves discoverability and reduces confusion.

---

## LOW IMPACT / LOW EFFORT (Delightful Details)

### 16. Add Keyboard Shortcuts

**Current:** Only Escape to clear model selection (`Models.tsx:194-201`).

**Recommendation:** Add global keyboard shortcuts:
- `g r` → Go to Run Config
- `g l` → Go to Live Monitor
- `g e` → Go to Results Explorer
- `g o` → Go to Observatory
- `g h` → Go to History
- `g p` → Go to Pipeline
- `g m` → Go to Models
- `?` → Show keyboard shortcuts modal

**File:** NEW `src/hooks/useKeyboardShortcuts.ts`, `App.tsx`

**Priority: LOW** — Power user delight feature.

---

### 17. Add "Last Updated" Timestamp to Data-Heavy Pages

**Current:** No indication of data freshness.

**Recommendation:** Add a subtle "Updated 3s ago" indicator in the page header area, pulsing gently when data is stale. Use React Query's `dataUpdatedAt` field.

**Files:** `Observatory.tsx`, `History.tsx`, `Models.tsx`

**Priority: LOW** — Nice trust signal for data-heavy pages.

---

### 18. Pipeline View Phase Cards Need Visual Flow

**Current:** (`PipelineView.tsx:112-165`) Phase cards are connected by a plain `→` text character.

**Problem:** The pipeline flow visualization is the weakest visual in the dashboard. It should look like a process diagram, not text with arrows.

**Recommendation:**
- Replace `→` text with an SVG connector line with a goldenrod arrowhead
- Add a subtle dashed line for incomplete/future phases
- Add a pulsing dot on the currently active phase's connector
- Consider a step indicator above: `● ─── ○ ─── ○` style progress

```
+------------+     →     +------------+     - - →     +------------+
| Screening  |  ────●───▶| Confirm    |  ─ ─ ─ ─ ─ ▷| Refinement |
| ✓ Complete |           | ◈ Active   |              | ○ Pending  |
+------------+           +------------+              +------------+
```

**File:** `PipelineView.tsx:154-159`

**Priority: MEDIUM** — This page is unique to Compass; make it visually distinctive.

---

### 19. FadeIn Delay Multiplier Is Too Subtle

**Current:** (`FadeIn.tsx`) Delay multiplier is `delay * 50ms`. With delays of 1-4, elements animate in at 50ms, 100ms, 150ms, 200ms apart.

**Problem:** 50ms per step is barely perceptible. The stagger feels simultaneous rather than cascading.

**Recommendation:** Increase to `delay * 80ms` or `delay * 100ms` for a more noticeable, premium stagger effect. Also increase the animation duration from 350ms to 400ms for a smoother feel.

**Files:** `FadeIn.tsx:13` (change multiplier), `tailwind.config.ts:97` (change animation duration)

**Priority: LOW** — Subtle tuning.

---

### 20. RunConfig Mode Selector Needs Selected State Emphasis

**Current:** (`RunConfig.tsx:62-93`) The Taguchi/Full radio buttons use a border color change and 5% background tint.

**Problem:** The selected state is too subtle. It should be more obviously "chosen."

**Recommendations:**
- **Add a check icon** in the top-right corner of the selected card (using the CompassCheckbox or a simple check circle)
- **Increase background tint** from `bg-brand-goldenrod/5` to `bg-brand-goldenrod/10`
- **Add a subtle inner shadow** or gradient on the selected card
- **Scale selected card slightly:** `scale-[1.02]` with transition

**File:** `RunConfig.tsx:66-72`

**Priority: LOW** — Only affects one page, but it's the first page users see.

---

## CROSS-CUTTING IMPROVEMENTS

### 21. Inconsistent Page Max-Width

**Pages using `max-w-wide` (1280px):** RunConfig, LiveMonitor, ResultsExplorer, Observatory, FactorAnalysis, PipelineView
**Pages using `max-w-full`:** History, Models

**Recommendation:** Standardize. History and Models use full width because they have wide tables, which is correct. But they should still have some max-width constraint to prevent extreme stretching on ultra-wide monitors. Use `max-w-[1600px]` or `max-w-full` with `2xl:max-w-[1600px]`.

**Files:** `History.tsx:131`, `Models.tsx:262`

---

### 22. Missing `<title>` Per Page

**Current:** No page-level `<title>` changes. The browser tab always shows whatever the HTML file sets.

**Recommendation:** Add `document.title` updates in each page component using a `useEffect` or a simple `useTitle` hook:
```tsx
useEffect(() => { document.title = "Observatory - Models"; }, []);
```

**Files:** All page components.

---

### 23. CompassCheckbox Inline Styles Should Move to globals.css

**Current:** (`CompassCheckbox.tsx:59-78`) CSS animations are defined inline via a `<style>` tag. This means the CSS is duplicated for every CompassCheckbox instance in the DOM.

**Recommendation:** Move the `@keyframes compass-draw-check` and associated classes to `globals.css`.

**File:** `CompassCheckbox.tsx:59-78` → `globals.css`

---

### 24. Filter Range Slider Needs Visual Upgrade

**Current:** (`FilterPanel.tsx:80-89`) Uses native `<input type="range">` with just `accent-brand-goldenrod`.

**Problem:** Native range inputs are the least styled interactive element. The track is thin, the thumb is a generic circle.

**Recommendation:** Add custom range slider styles in globals.css:
```css
input[type="range"] {
  -webkit-appearance: none;
  height: 4px;
  background: theme("colors.brand.mist");
  border-radius: 9999px;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: theme("colors.brand.goldenrod");
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
```

**File:** `globals.css`

---

## ACCESSIBILITY & RESPONSIVE GAPS

### 25. Focus States Are Good but Missing `focus-visible` Styling on Some Elements

**Good:** `globals.css:30-33` applies goldenrod focus ring globally.
**Gap:** Some interactive elements override this with custom focus styles that may not be as visible:
- `FilterPanel.tsx:41` checkbox has ring but no offset
- `SlideOutPanel.tsx:45` close button has no explicit focus style

**Recommendation:** Audit all custom focus styles to ensure they meet WCAG 2.1 AA contrast ratios. The global `focus-visible` rule is good but some elements may need `outline-offset: 3px` for adequate spacing.

---

### 26. Touch Target Minimum on Mobile

**Good:** `globals.css:46-49` sets `min-height: 44px; min-width: 44px` on interactive elements.
**Gap:** The ViewMode toggle buttons in Models (`Models.tsx:379-402`) have `p-sp-2` (8px) padding which, combined with the 20px icon, gives a 36px visual target. The min-height CSS rule will override this, but visually it may look cramped.

**Recommendation:** Increase padding to `p-sp-3` (12px) for a more comfortable 44px visual target.

---

### 27. Responsive Breakpoint Coverage

**Gaps identified:**
- `Models.tsx` sidebar (`w-[264px]`) has no responsive behavior — on mobile it would crush the main content area. Add `hidden lg:block` and a filter toggle button for mobile.
- `PipelineView.tsx:112` uses `flex items-stretch gap-sp-4` for phase cards — on narrow screens these won't wrap. Add `flex-wrap` or switch to a vertical layout on mobile.
- `History.tsx` compare table has no horizontal scroll wrapper on narrow screens.

---

## SUMMARY TABLE

| # | Recommendation | Effort | Impact | Files |
|---|---------------|--------|--------|-------|
| 1 | Skeleton loading screens | Medium | Highest | NEW + all pages |
| 2 | Animated number counters | Low | High | NEW + 3 pages |
| 3 | Nav bar brand personality | Medium | High | App.tsx |
| 4 | Engaging empty states | Medium | High | NEW + 5+ locations |
| 5 | Route transition animation | Low | High | App.tsx |
| 6 | Wire up ScrollThread | Trivial | High | App.tsx (2 lines) |
| 7 | DataTable interactive polish | Medium | Medium | DataTable.tsx |
| 8 | Card variants (interactive/stat) | Medium | Medium | Card.tsx + all pages |
| 9 | Custom Select component | High | Medium | NEW + 4 pages |
| 10 | Chart entry animations | Low | Medium | 6 chart option objects |
| 11 | Live progress bar shimmer | Low | Medium | LiveMonitor.tsx |
| 12 | Custom scrollbars | Low | Medium | globals.css |
| 13 | Button press feedback | Trivial | Low-Med | Button.tsx |
| 14 | Animated tab underlines | Medium | Medium | 2 pages |
| 15 | Tooltip system | Medium | Medium | NEW + many locations |
| 16 | Keyboard shortcuts | Medium | Low | NEW hook + App.tsx |
| 17 | "Last Updated" indicators | Low | Low | 3 pages |
| 18 | Pipeline visual connectors | Medium | Medium | PipelineView.tsx |
| 19 | FadeIn timing adjustment | Trivial | Low | FadeIn.tsx, tailwind.config |
| 20 | RunConfig mode emphasis | Low | Low | RunConfig.tsx |
| 21 | Consistent page max-width | Trivial | Low | 2 pages |
| 22 | Per-page document.title | Trivial | Low | All pages |
| 23 | CompassCheckbox CSS cleanup | Low | Low | CompassCheckbox, globals.css |
| 24 | Range slider styling | Low | Low | globals.css |

---

## RECOMMENDED IMPLEMENTATION ORDER

**Sprint 1 (Quick Wins):**
1. Wire up ScrollThread (item 6) — 2 minutes
2. Chart entry animations (item 10) — 15 minutes
3. Button press feedback (item 13) — 5 minutes
4. FadeIn timing (item 19) — 2 minutes
5. Custom scrollbars (item 12) — 10 minutes
6. Range slider styling (item 24) — 10 minutes

**Sprint 2 (Foundation):**
7. Skeleton loading component (item 1)
8. AnimatedNumber component (item 2)
9. Route transitions (item 5)
10. DataTable sort indicator fix (item 7, partial)

**Sprint 3 (Brand Polish):**
11. Nav bar personality (item 3)
12. EmptyState component (item 4)
13. Card variants (item 8)
14. CompassCheckbox CSS cleanup (item 23)

**Sprint 4 (Interaction Layer):**
15. Tooltip system (item 15)
16. Tab underline animation (item 14)
17. Custom Select component (item 9)
18. Pipeline visual connectors (item 18)

**Sprint 5 (Delight):**
19. Keyboard shortcuts (item 16)
20. Per-page titles (item 22)
21. "Last Updated" indicators (item 17)
22. Responsive fixes (items 25-27)
