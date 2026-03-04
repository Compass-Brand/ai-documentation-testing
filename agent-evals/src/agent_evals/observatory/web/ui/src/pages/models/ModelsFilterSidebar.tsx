import { m, AnimatePresence } from "framer-motion";
import type { ModelFilters } from "../../api/client";
import {
  FilterSection,
  FilterCheckbox,
  FilterRange,
} from "../../components/FilterPanel";
import { ProviderCombobox } from "../../components/ProviderCombobox";
import { Input } from "../../components/Input";
import { FadeIn } from "../../components/FadeIn";
import { CompassRose } from "../../components/CompassRose";


interface ModelsFilterSidebarProps {
  searchRef: React.Ref<HTMLInputElement>;
  searchTerm: string;
  onSearchChange: (term: string) => void;
  showHint: boolean;
  filters: ModelFilters;
  setFilters: (f: Partial<ModelFilters>) => void;
  providers: Array<{ name: string; count: number }>;
  selectedProviders: Set<string>;
  onProviderChange: (providers: Set<string>) => void;
  total: number;
  hasActiveFilters: boolean;
  onClearAll: () => void;
}

export function FilterContent({
  filters,
  setFilters,
  providers,
  selectedProviders,
  onProviderChange,
}: Pick<
  ModelsFilterSidebarProps,
  "filters" | "setFilters" | "providers" | "selectedProviders" | "onProviderChange"
>) {
  return (
    <>
      <FilterSection label="Pricing">
        <FilterCheckbox
          label="Free models only"
          checked={filters.free ?? false}
          onCheckedChange={(checked) =>
            setFilters({ free: checked || undefined })
          }
        />
        <FilterRange
          label="Max price per 1M tokens"
          min={0}
          max={100}
          value={[0, filters.maxPrice ?? 100]}
          onChange={([, max]) => setFilters({ maxPrice: max })}
          format={(n) => `$${n}`}
        />
      </FilterSection>

      <FilterSection label="Context Length">
        <FilterRange
          label="Min context length"
          min={0}
          max={1000}
          value={[filters.minContext ? filters.minContext / 1000 : 0, 1000]}
          onChange={([min]) =>
            setFilters({ minContext: min > 0 ? min * 1000 : undefined })
          }
          format={(n) => `${n}k`}
        />
      </FilterSection>

      <FilterSection label="Modality">
        {["text->text", "text+image->text", "text->image"].map((m) => (
          <FilterCheckbox
            key={m}
            label={m}
            checked={filters.modality === m}
            onCheckedChange={(checked) =>
              setFilters({ modality: checked ? m : undefined })
            }
          />
        ))}
      </FilterSection>

      <FilterSection label="Provider">
        <ProviderCombobox
          providers={providers}
          selected={selectedProviders}
          onSelectionChange={onProviderChange}
        />
      </FilterSection>
    </>
  );
}

export function ModelsFilterSidebar({
  searchRef,
  searchTerm,
  onSearchChange,
  showHint,
  filters,
  setFilters,
  providers,
  selectedProviders,
  onProviderChange,
  total,
  hasActiveFilters,
  onClearAll,
}: ModelsFilterSidebarProps) {
  return (
    <aside className="hidden lg:block w-[264px] shrink-0 relative">
      <div
        className="absolute inset-0 flex items-center justify-center overflow-hidden"
        data-compass-rose
      >
        <CompassRose />
      </div>
      <FadeIn delay={1}>
        <div className="relative bg-white/95 rounded-card p-sp-4 -m-sp-4">
          <Input
            ref={searchRef}
            placeholder="Search models..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <AnimatePresence>
            {showHint && (
              <m.kbd
                initial={{ opacity: 1, scale: 1 }}
                animate={{ scale: [1, 1.1, 1] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.6, delay: 1 }}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-brand-mist text-brand-slate text-xs font-mono px-1.5 py-0.5 rounded"
              >
                /
              </m.kbd>
            )}
          </AnimatePresence>
        </div>

        <div className="mt-sp-6">
          <FilterContent
            filters={filters}
            setFilters={setFilters}
            providers={providers}
            selectedProviders={selectedProviders}
            onProviderChange={onProviderChange}
          />

          <p className="text-caption text-brand-slate mt-sp-4">
            {total} models found
            {hasActiveFilters && (
              <button
                className="ml-sp-2 text-brand-goldenrod hover:underline"
                onClick={onClearAll}
              >
                Clear all
              </button>
            )}
          </p>
        </div>
      </FadeIn>
    </aside>
  );
}
