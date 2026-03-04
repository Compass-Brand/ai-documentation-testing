import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import * as Popover from "@radix-ui/react-popover";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ChevronDown, X, Search } from "lucide-react";
import { cn } from "../lib/utils";

const PROVIDER_COLORS = [
  "#C2A676", // goldenrod
  "#8B9D83", // sage
  "#D4A574", // amber
  "#B85C4A", // clay
  "#6B7B8D", // slate
  "#E8DDD0", // bone
];

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getProviderColor(name: string): string {
  return PROVIDER_COLORS[hashString(name) % PROVIDER_COLORS.length];
}

interface ProviderComboboxProps {
  providers: Array<{ name: string; count: number }>;
  selected: Set<string>;
  onSelectionChange: (selected: Set<string>) => void;
}

const MAX_VISIBLE_PILLS = 3;

const pillVariants = {
  initial: { opacity: 0, scale: 0.8 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.8 },
};

const dropdownVariants = {
  initial: { opacity: 0, scale: 0.95 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 400, damping: 25 },
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    transition: { duration: 0.15 },
  },
};

const checkVariants = {
  initial: { opacity: 0, scale: 0 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0 },
};

export function ProviderCombobox({
  providers,
  selected,
  onSelectionChange,
}: ProviderComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const [flashedProvider, setFlashedProvider] = useState<string | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const flashTimer = useRef<ReturnType<typeof setTimeout>>();

  // Clean up flash timer on unmount
  useEffect(() => {
    return () => clearTimeout(flashTimer.current);
  }, []);

  const filteredProviders = useMemo(
    () => providers.filter((p) => p.name.toLowerCase().includes(search.toLowerCase())),
    [providers, search],
  );

  // Reset highlight and search when dropdown opens/closes
  useEffect(() => {
    if (open) {
      setSearch("");
      setHighlightIndex(-1);
      // Focus search input after popover animation starts
      requestAnimationFrame(() => {
        searchInputRef.current?.focus();
      });
    }
  }, [open]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIndex >= 0) {
      const el = itemRefs.current.get(highlightIndex);
      el?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightIndex]);

  const toggleProvider = useCallback(
    (providerName: string) => {
      const key = providerName.toLowerCase();
      const next = new Set(selected);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      onSelectionChange(next);

      // Flash highlight
      clearTimeout(flashTimer.current);
      setFlashedProvider(key);
      flashTimer.current = setTimeout(() => setFlashedProvider(null), 400);
    },
    [selected, onSelectionChange],
  );

  const removePill = useCallback(
    (providerKey: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const next = new Set(selected);
      next.delete(providerKey);
      onSelectionChange(next);
    },
    [selected, onSelectionChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open) return;

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          setHighlightIndex((prev) =>
            prev < filteredProviders.length - 1 ? prev + 1 : 0,
          );
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          setHighlightIndex((prev) =>
            prev > 0 ? prev - 1 : filteredProviders.length - 1,
          );
          break;
        }
        case "Enter":
        case " ": {
          if (highlightIndex >= 0 && highlightIndex < filteredProviders.length) {
            e.preventDefault();
            toggleProvider(filteredProviders[highlightIndex].name);
          }
          break;
        }
        case "Escape": {
          e.preventDefault();
          setOpen(false);
          break;
        }
        default:
          break;
      }
    },
    [open, highlightIndex, filteredProviders, toggleProvider],
  );

  const selectedArray = Array.from(selected);
  const visiblePills = selectedArray.slice(0, MAX_VISIBLE_PILLS);
  const overflowCount = selectedArray.length - MAX_VISIBLE_PILLS;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className={cn(
            "flex w-full items-center gap-sp-2 rounded-card border bg-brand-bone",
            "px-sp-3 py-sp-2 text-body-sm text-brand-charcoal",
            "transition-colors duration-micro",
            "focus-visible:border-brand-goldenrod focus-visible:outline-none",
            "focus-visible:ring-2 focus-visible:ring-brand-goldenrod/20",
            open ? "border-brand-goldenrod" : "border-brand-mist",
          )}
        >
          <div className="flex flex-1 flex-wrap items-center gap-sp-1 min-h-[24px]">
            {selectedArray.length === 0 && (
              <span className="text-brand-slate/60">Filter by provider...</span>
            )}
            <AnimatePresence mode="popLayout">
              {visiblePills.map((key) => {
                const provider = providers.find(
                  (p) => p.name.toLowerCase() === key,
                );
                const displayName = provider?.name ?? key;
                return (
                  <motion.span
                    key={key}
                    variants={pillVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    layout
                    className={cn(
                      "inline-flex items-center gap-sp-1 rounded-full",
                      "bg-brand-goldenrod/10 px-sp-2 py-0.5",
                      "text-caption font-medium text-brand-charcoal",
                    )}
                  >
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: getProviderColor(displayName) }}
                    />
                    {displayName}
                    <button
                      type="button"
                      className="ml-0.5 rounded-full p-0.5 text-brand-slate hover:text-brand-charcoal hover:bg-brand-goldenrod/20 transition-colors duration-micro"
                      onClick={(e) => removePill(key, e)}
                      aria-label={`Remove ${displayName}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </motion.span>
                );
              })}
              {overflowCount > 0 && (
                <motion.span
                  key="overflow"
                  variants={pillVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  layout
                  className={cn(
                    "inline-flex items-center rounded-full",
                    "bg-brand-mist px-sp-2 py-0.5",
                    "text-caption font-medium text-brand-slate",
                  )}
                >
                  +{overflowCount} more
                </motion.span>
              )}
            </AnimatePresence>
          </div>

          <motion.div
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className="shrink-0 text-brand-slate"
          >
            <ChevronDown className="h-4 w-4" />
          </motion.div>
        </button>
      </Popover.Trigger>

      <AnimatePresence>
        {open && (
          <Popover.Portal forceMount>
            <Popover.Content
              asChild
              align="start"
              sideOffset={4}
              className="z-50"
              onKeyDown={handleKeyDown}
            >
              <motion.div
                variants={dropdownVariants}
                initial="initial"
                animate="animate"
                exit="exit"
                className={cn(
                  "w-[var(--radix-popover-trigger-width)] rounded-card border border-brand-mist",
                  "bg-white shadow-lg",
                  "origin-top",
                )}
              >
                {/* Search input */}
                <div className="flex items-center gap-sp-2 border-b border-brand-mist px-sp-3 py-sp-2">
                  <Search className="h-4 w-4 text-brand-slate shrink-0" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setHighlightIndex(-1);
                    }}
                    placeholder="Search providers..."
                    className={cn(
                      "w-full bg-transparent text-body-sm text-brand-charcoal",
                      "placeholder:text-brand-slate/60",
                      "focus:outline-none",
                    )}
                  />
                </div>

                {/* Provider list */}
                <div
                  ref={listRef}
                  role="listbox"
                  aria-multiselectable="true"
                  className="max-h-[240px] overflow-y-auto py-sp-1"
                >
                  {filteredProviders.length === 0 && (
                    <p className="px-sp-3 py-sp-4 text-center text-caption text-brand-slate">
                      No providers match "{search}"
                    </p>
                  )}
                  {filteredProviders.map((provider, index) => {
                    const key = provider.name.toLowerCase();
                    const isSelected = selected.has(key);
                    const isHighlighted = highlightIndex === index;
                    const isFlashed = flashedProvider === key;

                    return (
                      <button
                        key={provider.name}
                        ref={(el) => {
                          if (el) itemRefs.current.set(index, el);
                          else itemRefs.current.delete(index);
                        }}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => toggleProvider(provider.name)}
                        onMouseEnter={() => setHighlightIndex(index)}
                        className={cn(
                          "flex w-full items-center gap-sp-3 px-sp-3 py-sp-2",
                          "text-body-sm text-brand-charcoal",
                          "transition-colors duration-micro",
                          isHighlighted && "bg-brand-cream",
                          isFlashed && "bg-brand-goldenrod/10",
                        )}
                      >
                        <span
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{
                            backgroundColor: getProviderColor(provider.name),
                          }}
                        />
                        <span className="flex-1 text-left">
                          {provider.name}{" "}
                          <span className="text-brand-slate">
                            ({provider.count})
                          </span>
                        </span>
                        <div className="w-4 h-4 flex items-center justify-center shrink-0">
                          <AnimatePresence>
                            {isSelected && (
                              <motion.div
                                variants={checkVariants}
                                initial="initial"
                                animate="animate"
                                exit="exit"
                                transition={{
                                  type: "spring",
                                  stiffness: 500,
                                  damping: 25,
                                }}
                              >
                                <Check className="h-4 w-4 text-brand-goldenrod" />
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </motion.div>
            </Popover.Content>
          </Popover.Portal>
        )}
      </AnimatePresence>
    </Popover.Root>
  );
}
