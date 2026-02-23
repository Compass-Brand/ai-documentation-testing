# Observatory Frontend Implementation Spec

**Date:** 2026-02-23
**Status:** Draft
**Depends on:** [Brand Guidelines v4.0](../../../../docs/brand/brand-guidelines.md), [Taguchi Multimodel Observatory Design](2026-02-17-taguchi-multimodel-observatory-design.md)

---

## 1. Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | React | 18+ | Component architecture |
| Build | Vite | 5+ | Dev server and production bundling |
| Styling | TailwindCSS | 3+ | Utility-first CSS with brand tokens |
| Components | Radix UI + shadcn/ui | latest | Accessible primitive components |
| Charts | Chart.js + react-chartjs-2 | 4+ | Live dashboard charts |
| Report Charts | Plotly.js | 5+ | Static HTML report visualizations |
| Icons | Lucide React | latest | Thin line icons (1.5px stroke) |
| State | TanStack Query v5 | latest | Server state and SSE subscriptions |
| Tables | TanStack Table v8 | latest | Sortable, selectable data tables |
| Type Safety | TypeScript | 5+ | Type checking |
| Testing | Vitest | latest | Unit and component tests |
| Routing | React Router v6 | latest | Client-side routing |

---

## 2. Directory Structure

```
agent-evals/src/agent_evals/observatory/web/ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html
├── src/
│   ├── main.tsx              # Entry point, React root
│   ├── App.tsx               # Shell with nav + routes
│   ├── api/
│   │   ├── client.ts         # Typed fetch wrapper + all endpoints
│   │   └── hooks.ts          # TanStack Query hooks
│   ├── components/
│   │   ├── Button.tsx         # Primary, secondary, ghost, danger
│   │   ├── Card.tsx           # Card, CardHeader, CardTitle, CardContent
│   │   ├── DataTable.tsx      # Sortable, selectable table (TanStack)
│   │   ├── StatusBadge.tsx    # Color-coded status labels
│   │   ├── SlideOutPanel.tsx  # Right-side detail drawer (Radix Dialog)
│   │   ├── FilterPanel.tsx    # FilterSection, FilterCheckbox, FilterRange
│   │   ├── FadeIn.tsx         # Page-load stagger animation
│   │   └── AccessibleChart.tsx
│   ├── pages/
│   │   ├── RunConfig.tsx      # Page 1: start new evaluations
│   │   ├── LiveMonitor.tsx    # Page 2: SSE-driven live progress
│   │   ├── ResultsExplorer.tsx # Page 3: run analysis + charts
│   │   ├── Observatory.tsx    # Page 4: cost telemetry
│   │   ├── History.tsx        # Page 5: cross-run trends
│   │   └── Models.tsx         # Page 6: model browser + groups
│   ├── hooks/
│   │   ├── useSSE.ts          # EventSource wrapper with auto-reconnect
│   │   └── useFilterParams.ts # URL-synced filter state
│   ├── lib/
│   │   ├── utils.ts           # cn() helper (clsx + twMerge)
│   │   ├── chart-theme.ts     # Chart.js brand defaults + color palette
│   │   └── motion.ts          # Transition presets
│   └── styles/
│       └── globals.css        # Tailwind directives + semantic tokens
├── public/
└── dist/                      # Build output, served by FastAPI
```

FastAPI serves `dist/` as static files. A catch-all route returns `index.html` for client-side routing.

---

## 3. Tailwind Brand Configuration

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          charcoal: "#1A1A1A",    // Primary dark background
          cream: "#F7F5F0",       // Primary light background
          goldenrod: "#C2A676",   // Primary action color
          sage: "#4A5D4E",        // Success states
          slate: "#5C6B7F",       // Muted text, inactive icons
          bone: "#FFFFFF",        // Card backgrounds, text on dark
          clay: "#A05040",        // Error/alert
          mist: "#E5E5E5",        // Subtle borders
          amber: "#D4A84B",       // Warning, in-progress
        },
      },
      fontFamily: {
        display: [
          "Playfair Display", "Georgia", "Times New Roman", "serif",
        ],
        sans: [
          "Inter", "DM Sans", "-apple-system", "BlinkMacSystemFont",
          "Segoe UI", "sans-serif",
        ],
      },
      fontSize: {
        display: ["72px", { lineHeight: "1.1", fontWeight: "700" }],
        h1: ["48px", { lineHeight: "1.2", fontWeight: "700" }],
        h2: ["36px", { lineHeight: "1.25", fontWeight: "600" }],
        h3: ["30px", { lineHeight: "1.3", fontWeight: "600" }],
        h4: ["24px", { lineHeight: "1.4", fontWeight: "500" }],
        h5: ["20px", { lineHeight: "1.4", fontWeight: "500" }],
        "body-lg": ["18px", { lineHeight: "1.7" }],
        body: ["16px", { lineHeight: "1.6" }],
        "body-sm": ["14px", { lineHeight: "1.5" }],
        caption: ["12px", { lineHeight: "1.4" }],
        data: ["11px", { lineHeight: "1.3", fontFamily: "monospace" }],
      },
      spacing: {
        "sp-1": "4px",
        "sp-2": "8px",
        "sp-3": "12px",
        "sp-4": "16px",
        "sp-5": "20px",
        "sp-6": "24px",
        "sp-8": "32px",
        "sp-10": "40px",
        "sp-12": "48px",
        "sp-16": "64px",
        "sp-20": "80px",
        "sp-24": "96px",
        "sp-32": "128px",
      },
      letterSpacing: {
        headline: "-0.02em",
        normal: "0",
        caps: "0.05em",
      },
      borderRadius: {
        pill: "9999px",
        card: "8px",
      },
      boxShadow: {
        card: "0 4px 20px rgba(0, 0, 0, 0.05)",
        "card-hover": "0 8px 30px rgba(0, 0, 0, 0.08)",
        panel: "0 8px 40px rgba(0, 0, 0, 0.12)",
      },
      maxWidth: {
        narrow: "640px",
        default: "1024px",
        wide: "1280px",
        full: "1400px",
      },
      transitionDuration: {
        micro: "150ms",
        state: "250ms",
        page: "350ms",
        modal: "250ms",
      },
      screens: {
        sm: "640px",
        md: "768px",
        lg: "1024px",
        xl: "1280px",
        "2xl": "1400px",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 350ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
```

---

## 4. Semantic Color Tokens

```css
/* globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Semantic aliases */
    --color-bg-primary: theme("colors.brand.cream");
    --color-bg-dark: theme("colors.brand.charcoal");
    --color-bg-card: theme("colors.brand.bone");
    --color-text-primary: theme("colors.brand.charcoal");
    --color-text-inverse: theme("colors.brand.bone");
    --color-text-muted: theme("colors.brand.slate");
    --color-action: theme("colors.brand.goldenrod");
    --color-border: theme("colors.brand.mist");

    /* Status colors */
    --color-success: theme("colors.brand.sage");
    --color-warning: theme("colors.brand.amber");
    --color-error: theme("colors.brand.clay");
    --color-neutral: theme("colors.brand.slate");
    --color-active: theme("colors.brand.goldenrod");

    /* Focus ring */
    --focus-ring: 2px solid theme("colors.brand.goldenrod");
    --focus-offset: 2px;
  }

  /* Focus ring on all interactive elements */
  *:focus-visible {
    outline: 2px solid theme("colors.brand.goldenrod");
    outline-offset: 2px;
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }

  /* Minimum touch target */
  button, a, input, select, textarea, [role="button"], [role="tab"] {
    min-height: 44px;
    min-width: 44px;
  }
}
```

---

## 5. Chart.js Brand Theme

```typescript
// lib/chart-theme.ts
import { Chart, defaults } from "chart.js";

export function applyBrandTheme() {
  defaults.font.family = "Inter, sans-serif";
  defaults.font.size = 12;
  defaults.color = "#5C6B7F";              // Slate Horizon

  defaults.plugins.legend.labels.usePointStyle = true;
  defaults.plugins.legend.labels.padding = 16;

  defaults.scale.grid.color = "rgba(229, 229, 229, 0.5)"; // Mist Grey 50%
  defaults.scale.border.color = "#E5E5E5";
  defaults.scale.ticks.padding = 8;
}

export const CHART_COLORS = {
  primary: "#C2A676",     // Goldenrod — primary trend line
  secondary: "#5C6B7F",   // Slate — secondary data
  success: "#4A5D4E",     // Sage
  warning: "#D4A84B",     // Amber
  error: "#A05040",       // Clay
  grid: "rgba(229, 229, 229, 0.5)",
} as const;

export const CHART_LINE_WIDTHS = {
  primary: 2,
  secondary: 1,
  grid: 1,
} as const;

export const CHART_BACKGROUNDS = {
  transparent: "transparent",
  subtle: "rgba(74, 93, 78, 0.05)", // 5% Sage Wisdom
} as const;

export const CHART_PROJECTION = {
  borderDash: [6, 4],
  borderColor: "#1A1A1A", // Deep Charcoal
  borderWidth: 1,
} as const;
```

### Chart Styling Rules

| Element | Style |
|---------|-------|
| Primary trend line | Goldenrod Ochre, 2px |
| Secondary data | Slate Horizon, 1px |
| Grid lines | Mist Grey 50% opacity |
| Font | Inter, 12px (Caption size) |
| Point radius | 0 (line charts), 4 (scatter) |
| Fill | Primary color at 15% opacity |
| Border radius (bar) | 4px |
| Background | Transparent or 5% opacity Sage Wisdom |
| Projection line | Dotted, Deep Charcoal |

---

## 6. Component Library

### Button

Pill-shaped buttons using `class-variance-authority` for variants.

```tsx
// components/Button.tsx
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center font-medium",
    "transition-all duration-micro ease-out",
    "focus-visible:outline-none focus-visible:ring-2",
    "focus-visible:ring-brand-goldenrod focus-visible:ring-offset-2",
    "disabled:opacity-50 disabled:pointer-events-none",
  ].join(" "),
  {
    variants: {
      variant: {
        primary: [
          "bg-brand-goldenrod text-brand-charcoal rounded-pill",
          "hover:brightness-105 hover:shadow-card-hover hover:-translate-y-px",
          "active:translate-y-0 active:brightness-95",
        ].join(" "),
        secondary: [
          "bg-transparent text-brand-charcoal border border-brand-charcoal rounded-pill",
          "hover:bg-brand-cream",
        ].join(" "),
        ghost:
          "text-brand-slate hover:text-brand-charcoal hover:bg-brand-cream rounded-card",
        danger: [
          "bg-brand-clay text-brand-bone rounded-pill",
          "hover:brightness-110 hover:shadow-card-hover hover:-translate-y-px",
          "active:translate-y-0 active:brightness-95",
        ].join(" "),
      },
      size: {
        sm: "h-8 px-sp-4 text-body-sm",
        md: "h-11 px-sp-6 text-body",        // 44px min touch target
        lg: "h-[52px] px-sp-8 text-body-lg",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
```

### Card

```tsx
// components/Card.tsx
import { cn } from "../lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "bg-brand-bone rounded-card p-sp-6 shadow-card",
        "transition-shadow duration-state",
        "hover:shadow-card-hover",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("mb-sp-4", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<
  HTMLHeadingElement,
  HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-h4 text-brand-charcoal", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("text-body text-brand-slate", className)}
      {...props}
    />
  ),
);
CardContent.displayName = "CardContent";
```

### DataTable

Sortable, selectable data table using TanStack Table.

```tsx
// components/DataTable.tsx
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  onSelectionChange?: (selected: T[]) => void;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  selectable,
  onSelectionChange,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [rowSelection, setRowSelection] = useState({});

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    onRowSelectionChange: (updater) => {
      setRowSelection(updater);
      if (onSelectionChange) {
        const next =
          typeof updater === "function" ? updater(rowSelection) : updater;
        const selected = Object.keys(next)
          .filter((k) => next[k as keyof typeof next])
          .map((k) => data[parseInt(k)]);
        onSelectionChange(selected);
      }
    },
    enableRowSelection: selectable,
    state: { sorting, rowSelection },
  });

  return (
    <div className="overflow-x-auto rounded-card border border-brand-mist">
      <table className="w-full text-body-sm">
        <thead className="bg-brand-cream">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className={cn(
                    "px-sp-4 py-sp-3 text-left font-medium text-brand-slate",
                    header.column.getCanSort() &&
                      "cursor-pointer select-none",
                  )}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  <span className="inline-flex items-center gap-sp-2">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                    {header.column.getCanSort() && (
                      <ArrowUpDown className="h-4 w-4 text-brand-slate/50" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={cn(
                "border-t border-brand-mist transition-colors duration-micro",
                "hover:bg-brand-cream/50",
                onRowClick && "cursor-pointer",
                row.getIsSelected() && "bg-brand-goldenrod/10",
              )}
              onClick={() => onRowClick?.(row.original)}
            >
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className="px-sp-4 py-sp-3 text-brand-charcoal"
                >
                  {flexRender(
                    cell.column.columnDef.cell,
                    cell.getContext(),
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### StatusBadge

```tsx
// components/StatusBadge.tsx
import { cn } from "../lib/utils";

type Status = "success" | "warning" | "error" | "neutral" | "active" | "new";

const statusStyles: Record<Status, string> = {
  success: "bg-brand-sage/15 text-brand-sage",
  warning: "bg-brand-amber/15 text-brand-amber",
  error: "bg-brand-clay/15 text-brand-clay",
  neutral: "bg-brand-slate/15 text-brand-slate",
  active: "bg-brand-goldenrod/15 text-brand-goldenrod",
  new: "bg-brand-goldenrod text-brand-charcoal",
};

interface StatusBadgeProps {
  status: Status;
  label: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill px-sp-3 py-sp-1",
        "text-caption font-medium",
        statusStyles[status],
        className,
      )}
    >
      {label}
    </span>
  );
}
```

### SlideOutPanel

Right-side detail drawer using Radix Dialog for accessibility.

```tsx
// components/SlideOutPanel.tsx
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "../lib/utils";
import type { ReactNode } from "react";

interface SlideOutPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: "md" | "lg";
}

const widthClasses = {
  md: "w-[400px]",
  lg: "w-[500px]",
};

export function SlideOutPanel({
  open,
  onClose,
  title,
  children,
  width = "lg",
}: SlideOutPanelProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-brand-charcoal/30 transition-opacity duration-modal" />
        <Dialog.Content
          className={cn(
            "fixed right-0 top-0 h-full bg-brand-bone shadow-panel",
            "overflow-y-auto",
            "transition-transform duration-page ease-in-out",
            "data-[state=open]:translate-x-0",
            "data-[state=closed]:translate-x-full",
            widthClasses[width],
          )}
        >
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-brand-mist bg-brand-bone px-sp-6 py-sp-4">
            <Dialog.Title className="text-h4 text-brand-charcoal">
              {title}
            </Dialog.Title>
            <Dialog.Close className="rounded-card p-sp-2 text-brand-slate hover:bg-brand-cream hover:text-brand-charcoal transition-colors duration-micro">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <div className="p-sp-6">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### FilterPanel

```tsx
// components/FilterPanel.tsx
import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { cn } from "../lib/utils";
import type { ReactNode } from "react";

interface FilterSectionProps {
  label: string;
  children: ReactNode;
}

export function FilterSection({ label, children }: FilterSectionProps) {
  return (
    <div className="mb-sp-6">
      <h4 className="mb-sp-3 text-body-sm font-medium text-brand-charcoal">
        {label}
      </h4>
      {children}
    </div>
  );
}

interface FilterCheckboxProps {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

export function FilterCheckbox({
  label,
  checked,
  onCheckedChange,
}: FilterCheckboxProps) {
  return (
    <label className="flex cursor-pointer items-center gap-sp-3 py-sp-1 text-body-sm text-brand-slate hover:text-brand-charcoal transition-colors duration-micro">
      <Checkbox.Root
        checked={checked}
        onCheckedChange={(c) => onCheckedChange(c === true)}
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded border",
          "border-brand-mist transition-colors duration-micro",
          "focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
          "focus-visible:ring-offset-2",
          "data-[state=checked]:bg-brand-goldenrod",
          "data-[state=checked]:border-brand-goldenrod",
        )}
      >
        <Checkbox.Indicator>
          <Check className="h-3.5 w-3.5 text-brand-charcoal" />
        </Checkbox.Indicator>
      </Checkbox.Root>
      {label}
    </label>
  );
}

interface FilterRangeProps {
  label: string;
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  format?: (n: number) => string;
}

export function FilterRange({
  label,
  min,
  max,
  value,
  onChange,
  format,
}: FilterRangeProps) {
  const fmt = format ?? String;
  return (
    <div className="mb-sp-4">
      <div className="flex justify-between text-caption text-brand-slate mb-sp-2">
        <span>{fmt(value[0])}</span>
        <span>{fmt(value[1])}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value[1]}
        onChange={(e) => onChange([value[0], parseInt(e.target.value)])}
        className="w-full accent-brand-goldenrod"
        aria-label={label}
      />
    </div>
  );
}
```

### FadeIn (Page Load Animation)

```tsx
// components/FadeIn.tsx
import { cn } from "../lib/utils";

interface FadeInProps {
  children: React.ReactNode;
  delay?: number; // stagger index (0, 1, 2...)
  className?: string;
}

export function FadeIn({ children, delay = 0, className }: FadeInProps) {
  return (
    <div
      className={cn("animate-fade-in-up opacity-0", className)}
      style={{
        animationDelay: `${delay * 50}ms`,
        animationFillMode: "forwards",
      }}
    >
      {children}
    </div>
  );
}
```

### AccessibleChart

```tsx
// components/AccessibleChart.tsx
import type { ReactNode } from "react";

interface AccessibleChartProps {
  label: string;
  summary: string;
  children: ReactNode;
}

export function AccessibleChart({
  label,
  summary,
  children,
}: AccessibleChartProps) {
  return (
    <div role="img" aria-label={label}>
      <span className="sr-only">{summary}</span>
      {children}
    </div>
  );
}
```

---

## 7. API Client

```typescript
// api/client.ts
const BASE_URL = import.meta.env.VITE_API_URL ?? "";

async function fetchApi<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

// --- Type Definitions ---

export interface Run {
  run_id: string;
  run_type: string;
  status: "active" | "completed" | "failed";
  config: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface Trial {
  task_id: string;
  task_type: string;
  variant_name: string;
  repetition: number;
  score: number;
  metrics: Record<string, number>;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  latency_seconds: number;
  cached: boolean;
  error: string | null;
  source: string;
  model?: string;
  oa_row_id?: number;
}

export interface RunSummary {
  run: Run;
  total_trials: number;
  completed_trials: number;
  total_cost: number;
  total_tokens: number;
  mean_score: number;
  by_variant: Record<
    string,
    { mean_score: number; trial_count: number }
  >;
  by_model?: Record<
    string,
    { mean_score: number; trial_count: number; cost: number }
  >;
}

export interface ModelFilters {
  search?: string;
  free?: boolean;
  maxPrice?: number;
  minContext?: number;
  modality?: string;
  capability?: string;
  tokenizer?: string;
  sort?: string;
}

export interface Model {
  id: string;
  name: string;
  context_length: number;
  prompt_price: number;
  completion_price: number;
  modality: string;
  tokenizer: string;
  first_seen: number;
  last_seen: number;
  removed_at: number | null;
}

export interface ModelDetail extends Model {
  created: number;
  supported_params: string[];
}

export interface ProviderEndpoint {
  provider: string;
  latency_ms: number;
  uptime_pct: number;
  pricing_diff: number;
  quantization: string;
  supported_params: string[];
  zero_downtime_routing: boolean;
}

export interface ModelGroup {
  id: string;
  name: string;
  description: string;
}

export interface SyncStatus {
  total_models: number;
  last_sync: number;
  models_added: number;
  models_removed: number;
  models_updated: number;
}

export interface SyncResult {
  added: number;
  removed: number;
  updated: number;
}

// --- API Methods ---

export const api = {
  // Runs
  listRuns: () => fetchApi<Run[]>("/api/runs"),
  getRun: (id: string) => fetchApi<RunSummary>(`/api/runs/${id}`),
  getTrials: (id: string, model?: string) => {
    const params = model ? `?model=${encodeURIComponent(model)}` : "";
    return fetchApi<Trial[]>(`/api/runs/${id}/trials${params}`);
  },
  getReport: (id: string) =>
    fetchApi<Record<string, unknown>>(`/api/runs/${id}/report`),

  // Comparison and history
  compareRuns: (ids: string[]) =>
    fetchApi<Record<string, unknown>>(
      `/api/compare?ids=${ids.join(",")}`,
    ),
  costTrend: () =>
    fetchApi<Record<string, unknown>>("/api/history/cost-trend"),
  modelDrift: (model: string) =>
    fetchApi<Record<string, unknown>>(
      `/api/history/model-drift?model=${encodeURIComponent(model)}`,
    ),

  // Models
  listModels: (filters?: ModelFilters) => {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.free) params.set("free", "true");
    if (filters?.maxPrice != null)
      params.set("max_price", String(filters.maxPrice));
    if (filters?.minContext != null)
      params.set("min_context", String(filters.minContext));
    if (filters?.modality) params.set("modality", filters.modality);
    if (filters?.capability) params.set("capability", filters.capability);
    if (filters?.tokenizer) params.set("tokenizer", filters.tokenizer);
    if (filters?.sort) params.set("sort", filters.sort);
    const qs = params.toString();
    return fetchApi<{ models: Model[]; total: number }>(
      `/api/models${qs ? `?${qs}` : ""}`,
    );
  },
  getModel: (id: string) =>
    fetchApi<ModelDetail>(`/api/models/${encodeURIComponent(id)}`),
  getModelEndpoints: (id: string) =>
    fetchApi<{ endpoints: ProviderEndpoint[] }>(
      `/api/models/${encodeURIComponent(id)}/endpoints`,
    ),

  // Groups
  listGroups: () => fetchApi<ModelGroup[]>("/api/models/groups"),
  createGroup: (name: string, description: string) =>
    fetchApi<ModelGroup>("/api/models/groups", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  addGroupMembers: (groupId: string, modelIds: string[]) =>
    fetchApi<{ warnings: string[] }>(
      `/api/models/groups/${groupId}/members`,
      {
        method: "POST",
        body: JSON.stringify({ model_ids: modelIds }),
      },
    ),
  deleteGroup: (groupId: string) =>
    fetch(`${BASE_URL}/api/models/groups/${groupId}`, {
      method: "DELETE",
    }),

  // Sync
  syncStatus: () => fetchApi<SyncStatus>("/api/models/sync"),
  triggerSync: () =>
    fetchApi<SyncResult>("/api/models/sync", { method: "POST" }),
};
```

---

## 8. TanStack Query Hooks

```typescript
// api/hooks.ts
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api, type ModelFilters } from "./client";

// --- Runs ---
export function useRuns() {
  return useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
  });
}

export function useTrials(runId: string | null, model?: string) {
  return useQuery({
    queryKey: ["trials", runId, model],
    queryFn: () => api.getTrials(runId!, model),
    enabled: !!runId,
  });
}

export function useReport(runId: string | null) {
  return useQuery({
    queryKey: ["report", runId],
    queryFn: () => api.getReport(runId!),
    enabled: !!runId,
  });
}

// --- History ---
export function useCostTrend() {
  return useQuery({
    queryKey: ["cost-trend"],
    queryFn: api.costTrend,
  });
}

export function useModelDrift(model: string | null) {
  return useQuery({
    queryKey: ["model-drift", model],
    queryFn: () => api.modelDrift(model!),
    enabled: !!model,
  });
}

export function useCompareRuns(ids: string[]) {
  return useQuery({
    queryKey: ["compare", ids],
    queryFn: () => api.compareRuns(ids),
    enabled: ids.length >= 2,
  });
}

// --- Models ---
export function useModels(filters: ModelFilters) {
  return useQuery({
    queryKey: ["models", filters],
    queryFn: () => api.listModels(filters),
    keepPreviousData: true,
  });
}

export function useModelDetail(modelId: string | null) {
  return useQuery({
    queryKey: ["model", modelId],
    queryFn: () => api.getModel(modelId!),
    enabled: !!modelId,
  });
}

export function useModelEndpoints(modelId: string | null) {
  return useQuery({
    queryKey: ["model-endpoints", modelId],
    queryFn: () => api.getModelEndpoints(modelId!),
    enabled: !!modelId,
    refetchInterval: 60_000, // Auto-refresh every 60s per spec
  });
}

// --- Groups ---
export function useGroups() {
  return useQuery({ queryKey: ["groups"], queryFn: api.listGroups });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      description,
    }: {
      name: string;
      description: string;
    }) => api.createGroup(name, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useAddGroupMembers() {
  return useMutation({
    mutationFn: ({
      groupId,
      modelIds,
    }: {
      groupId: string;
      modelIds: string[];
    }) => api.addGroupMembers(groupId, modelIds),
  });
}

// --- Sync ---
export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: api.syncStatus,
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.triggerSync,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
  });
}
```

---

## 9. Custom Hooks

### SSE Hook (Live Monitor)

```typescript
// hooks/useSSE.ts
import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Trial } from "../api/client";

interface UseSSEOptions {
  runId: string | null;
  onTrialComplete?: (trial: Trial) => void;
  onRunComplete?: () => void;
  onError?: (error: string) => void;
}

export function useSSE({
  runId,
  onTrialComplete,
  onRunComplete,
  onError,
}: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const qc = useQueryClient();

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!runId) return;

    const baseUrl = import.meta.env.VITE_API_URL ?? "";
    const source = new EventSource(
      `${baseUrl}/api/runs/${runId}/stream`,
    );
    sourceRef.current = source;

    source.addEventListener("trial_completed", (e: MessageEvent) => {
      const trial: Trial = JSON.parse(e.data);
      onTrialComplete?.(trial);
      qc.invalidateQueries({ queryKey: ["run", runId] });
    });

    // Backend does not emit a run_complete event.
    // Poll the run summary to detect completion instead.
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(
          `${baseUrl}/api/runs/${runId}`,
        );
        if (res.ok) {
          const summary = await res.json();
          if (summary.status === "completed" || summary.status === "failed") {
            onRunComplete?.();
            qc.invalidateQueries({ queryKey: ["run", runId] });
            qc.invalidateQueries({ queryKey: ["trials", runId] });
            clearInterval(pollInterval);
            disconnect();
          }
        }
      } catch {
        // Ignore poll errors; SSE reconnects handle transient failures
      }
    }, 5000);

    source.addEventListener("error", () => {
      onError?.("SSE connection lost. Reconnecting...");
      // EventSource auto-reconnects by default
    });

    return () => {
      clearInterval(pollInterval);
      disconnect();
    };
  }, [runId, onTrialComplete, onRunComplete, onError, qc, disconnect]);

  return { disconnect };
}
```

### URL Filter State Hook

```typescript
// hooks/useFilterParams.ts
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
```

---

## 10. Pages

All six pages follow the same layout pattern:
- Max-width container with `px-sp-6 py-sp-8`
- `<h1>` with Lucide icon in Goldenrod and `text-h2`
- Cards on Savannah Cream background

Full page implementations are provided below by reference. Each page consumes the hooks from section 8 and composes the components from section 6.

### Page 1: Run Configuration (`/`)

Start new evaluation runs. Two-column form with mode selector (Taguchi/Full), model input, repetition count, task limit, and OA override. Mode selector uses radio cards with Goldenrod border on active. Submit navigates to Live Monitor.

### Page 2: Live Monitor (`/live/:runId`)

Real-time progress via SSE. Shows progress bar (Goldenrod fill on Mist background), four stat cards (mean score, total cost, trials/min, errors), rolling score trend chart (Chart.js line, Goldenrod primary, area fill at 15% opacity), and a scrollable recent trials feed with CheckCircle/AlertTriangle icons.

### Page 3: Results Explorer (`/results/:runId`)

Run analysis with run selector dropdown. Three summary stat cards, horizontal bar chart of variant scores (Chart.js), radar chart for model comparison (if multi-model), and a DataTable of variant breakdown with sortable columns.

### Page 4: Observatory (`/observatory`)

Cost telemetry. Three cost stat cards (total spend, total tokens, cost/trial), cumulative cost burn line chart, and a doughnut chart of cost by model.

### Page 5: History (`/history`)

Cross-run trends. Cost trend line chart across all runs, selectable run table with checkboxes for comparison, and a comparison result panel.

### Page 6: Models (`/models`)

Model browser with three-panel layout:
- **Left sidebar** (264px): Search input, pricing filter (free checkbox + range slider), context length range, modality checkboxes, capability checkboxes, live result count
- **Main content**: Toolbar with selection count + action buttons (Run Selected, Save as Group) + view toggle (table/cards). Table view uses DataTable with sortable columns. Card grid uses responsive 2-3 column layout with model name, price badge, modality badge, context info.
- **SlideOutPanel** (500px): Three tabs (Overview, Providers, History). Overview shows pricing grid, context/modality/tokenizer/status, capabilities badges, copyable API ID. Providers shows per-provider cards with color-coded latency (<100ms green, <500ms amber, >500ms red) and uptime, auto-refreshes every 60s. History shows first/last seen dates and deprecation status.

---

## 11. Accessibility

### WCAG 2.1 AA Compliance

| Combination | Ratio | Rating |
|-------------|-------|--------|
| Deep Charcoal on Savannah Cream | 12.6:1 | AAA |
| Bone White on Deep Charcoal | 15.1:1 | AAA |
| Goldenrod Ochre on Deep Charcoal | 6.2:1 | AA |
| Slate Horizon on Savannah Cream | 4.8:1 | AA |
| Sage Wisdom on Bone White | 5.1:1 | AA |
| Burnt Clay on Bone White | 5.4:1 | AA |

### Requirements

- All interactive elements reachable via Tab
- Radix UI handles arrow key navigation for menus, tabs, dialogs
- `Escape` closes SlideOutPanel and dialogs
- Charts include `aria-label` with text summary
- Status badges use `role="status"` for live updates
- Live Monitor trial feed uses `aria-live="polite"`
- Touch targets minimum 44x44px
- Focus ring: 2px solid Goldenrod Ochre with 2px offset

---

## 12. Motion Design

"Wind & Water" — smooth, easing like water flowing. No bouncy or elastic animations.

```typescript
// lib/motion.ts
export const TRANSITIONS = {
  micro: "transition-all duration-[150ms] ease-out",       // hover, focus
  state: "transition-all duration-[250ms] ease-in-out",    // tab switch, select
  page: "transition-all duration-[350ms] ease-in-out",     // route change
  modal: "transition-all duration-[250ms] ease-out",       // panel open
} as const;
```

| Element | Trigger | Animation |
|---------|---------|-----------|
| Button (primary) | Hover | `translateY(-1px)`, `brightness(1.05)`, 150ms |
| Button (primary) | Active | `translateY(0)`, instant |
| Card | Hover | Shadow card to card-hover, 250ms |
| SlideOutPanel | Open | `translateX(100% -> 0)`, 350ms |
| SlideOutPanel | Close | `translateX(0 -> 100%)`, 200ms ease-in |
| Dialog overlay | Open | Opacity 0 to 1, 250ms |
| Tab indicator | Switch | Border-bottom color, 150ms |
| Progress bar | Update | Width transition, 250ms |
| Page load | Mount | Elements drift up 20px with fade-in, staggered 50-100ms |

All animations respect `prefers-reduced-motion: reduce`.

---

## 13. Responsive Breakpoints

| Breakpoint | Nav | Filter Panel | Grid | SlideOutPanel |
|------------|-----|-------------|------|---------------|
| Mobile (0-639px) | Hamburger drawer | Hidden, toggle overlay | 1 column, cards only | Full-screen modal |
| sm (640px) | Hamburger drawer | Hidden, toggle overlay | 2 columns | Full-screen modal |
| md (768px) | Horizontal | Collapsible drawer | 2 columns | 400px |
| lg (1024px) | Horizontal | Always visible sidebar | 3-4 columns | 500px |
| xl (1280px) | Horizontal | Always visible sidebar | 3-4 columns | 500px |
| 2xl (1400px) | Horizontal | Always visible sidebar | 3-4 columns, centered | 500px |

---

## 14. Build and FastAPI Integration

### Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, "../static"),
    emptyDirBefore: true,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8501",
    },
  },
});
```

### FastAPI Static Serving

```python
# agent-evals/src/agent_evals/observatory/web/server.py
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

STATIC_DIR = Path(__file__).parent / "static"

def create_app(store, tracker, catalog, group_manager, model_sync):
    app = FastAPI(title="Observatory Dashboard")

    router = create_router(store, tracker, catalog, group_manager, model_sync)
    app.include_router(router)

    if STATIC_DIR.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=STATIC_DIR / "assets"),
            name="assets",
        )

        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            """Return index.html for client-side routing."""
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            return {"error": "Frontend not built. Run: npm run build"}

    return app
```

### Development Workflow

```bash
# One-time setup
cd agent-evals/src/agent_evals/observatory/web/ui
npm install
npm run build

# Development (hot reload)
# Terminal 1: Start backend
uv run agent-evals --mode taguchi --model ... --display plain

# Terminal 2: Start Vite dev server (proxies /api to :8501)
cd agent-evals/src/agent_evals/observatory/web/ui
npm run dev
# Open http://localhost:5173
```

---

## 15. API Endpoint Reference

| Endpoint | Method | Page | Purpose |
|----------|--------|------|---------|
| `/` | GET | — | Serve built React app |
| `/api/runs` | GET | Run Config, Results, Observatory, History | List all runs |
| `/api/runs/{run_id}` | GET | Live Monitor, Results, Observatory | Run summary |
| `/api/runs/{run_id}/trials` | GET | Results, Observatory | Trial data |
| `/api/runs/{run_id}/stream` | GET | Live Monitor | SSE live events |
| `/api/runs/{run_id}/report` | GET | Results | Report data |
| `/api/compare` | GET | History | Compare runs |
| `/api/history/cost-trend` | GET | History, Observatory | Cost trends |
| `/api/history/model-drift` | GET | History | Model drift |
| `/api/models` | GET | Models | List with filters |
| `/api/models/{model_id}` | GET | Models | Model detail |
| `/api/models/{model_id}/endpoints` | GET | Models | Provider data |
| `/api/models/groups` | GET/POST | Models | Group CRUD |
| `/api/models/groups/{id}/members` | POST | Models | Add to group |
| `/api/models/groups/{id}` | DELETE | Models | Delete group |
| `/api/models/sync` | GET/POST | Models | Sync status/trigger |

---

## 16. Additional Brand Elements

### The Thread (Scroll Progress Indicator)

Per the brand guidelines, a thin vertical Goldenrod line (`#C2A676`) runs along the left margin as a scroll progress indicator. Implement as a fixed-position element that fills proportionally to scroll position.

```tsx
// components/ScrollThread.tsx — optional brand-aligned scroll indicator
export function ScrollThread() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function onScroll() {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(total > 0 ? window.scrollY / total : 0);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="fixed left-0 top-0 z-50 h-full w-[2px] bg-brand-mist">
      <div
        className="w-full bg-brand-goldenrod transition-all duration-micro"
        style={{ height: `${progress * 100}%` }}
      />
    </div>
  );
}
```

### Dot Status Indicators

8px solid circles for inline status display, per brand guidelines:

```tsx
// components/StatusDot.tsx
const dotColors = {
  success: "bg-brand-sage",
  warning: "bg-brand-amber animate-pulse",
  error: "bg-brand-clay",
  syncing: "bg-brand-amber animate-pulse",
  offline: "bg-brand-slate",
} as const;

type DotStatus = keyof typeof dotColors;

export function StatusDot({ status }: { status: DotStatus }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${dotColors[status]}`}
      role="status"
      aria-label={status}
    />
  );
}
```

### Form Input

Follows the brand guidelines form input spec: Bone White background, Mist Grey border, Goldenrod focus ring, 8px border radius, 44px min height.

```tsx
// components/Input.tsx
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-11 w-full rounded-card border border-brand-mist bg-brand-bone",
      "px-sp-4 py-sp-3 text-body text-brand-charcoal",
      "placeholder:text-brand-slate/60",
      "focus:border-brand-goldenrod focus:outline-none focus:ring-2",
      "focus:ring-brand-goldenrod/20",
      "disabled:opacity-50 disabled:cursor-not-allowed",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
```

### Icon Guidelines

- Standard navigation icons: 20x20px, 1.5px stroke
- Inline icons: 16x16px
- Emphasis icons: 24x24px
- Use two-tone approach where appropriate: main stroke in Deep Charcoal or Bone White (context-dependent), accent fill detail in Goldenrod Ochre
- Prefer navigational/geometric metaphors (compasses, waypoints, nodes, grids)

### Glassmorphism Cards (Hero/Overlay Context)

For content overlaid on dark hero backgrounds:

```tsx
<div className="rounded-xl border border-white/20 bg-white/15 p-sp-6 backdrop-blur-[10px]">
  {children}
</div>
```

### Typography Letter Spacing

Applied via Tailwind `tracking-*` utilities:

- Headlines (Playfair Display): `tracking-headline` (-0.02em)
- Body text: `tracking-normal` (0)
- All-caps labels (e.g., table headers, badges): `tracking-caps` (0.05em)

---

## 17. Backend API Alignment Notes

The following discrepancies between this spec and the current backend implementation must be resolved during development. Either the frontend adapts to the backend, or the backend is updated to match.

| Area | Spec | Backend Reality | Resolution |
|------|------|----------------|------------|
| SSE event name | ~~`trial_complete`~~ `trial_completed` | `trial_completed` | **Fixed in spec** |
| Run completion | `run_complete` SSE event | No such event emitted | **Fixed in spec** — poll `/api/runs/{id}` instead |
| `POST /api/runs` | Run Config page needs it to start runs | Not implemented | Backend must add endpoint, or Run Config becomes CLI-only |
| `/api/runs/{id}/report` | Results page fetches report data | Endpoint exists but returns raw dict | Define response schema during implementation |
| `/api/compare` | History page compares runs | Endpoint exists | Verify response shape matches `useCompareRuns` expectations |
| `/api/runs/{id}` response | `RunSummary` with nested `run` object | `RunSummary` dataclass (flat) | Adapt frontend types to match actual `RunSummary` shape |
| Trial `model` field | Optional on `Trial` type | Present in `TrialResult.source` | Map `source` to model display name |
| Model endpoints | Full provider/latency data | Model catalog exists, endpoints TBD | Implement when OpenRouter provider data is available |
