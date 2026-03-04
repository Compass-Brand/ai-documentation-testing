import { useEffect, useMemo, useRef, useCallback, useState } from "react";
import { m, AnimatePresence } from "framer-motion";
import { Cpu } from "lucide-react";
import {
  useModels,
  useModelDetail,
  useModelEndpoints,
  useCreateGroup,
} from "../api/hooks";
import { useFilterParams } from "../hooks/useFilterParams";
import type { Model } from "../api/client";
import { FadeIn } from "../components/FadeIn";
import { SlideOutPanel } from "../components/SlideOutPanel";
import { Button } from "../components/Button";
import { ComparisonTray } from "../components/ComparisonTray";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { AmbientBackground } from "../components/AmbientBackground";
import { CursorGlow } from "../components/CursorGlow";
import {
  useModelsReducer,
  extractProviders,
  ModelsLoadingSkeleton,
  ModelsHeader,
  ModelsFilterSidebar,
  FilterContent,
  ModelsToolbar,
  ModelsTable,
  ModelsCardView,
  ModelDetailPanel,
} from "./models";

export function Models() {
  useDocumentTitle("Models");
  const [filters, setFilters] = useFilterParams();
  const { data: modelsData, isLoading } = useModels(filters);

  const {
    state,
    dispatch,
    toggleRow,
    selectAll,
    clearSelection,
    openDetail,
    closeDetail,
  } = useModelsReducer(filters.search ?? "");

  const { data: modelDetail } = useModelDetail(state.selectedModelId);
  const { data: endpointsData } = useModelEndpoints(state.selectedModelId);
  const createGroup = useCreateGroup();

  const models = modelsData?.models ?? [];
  const total = modelsData?.total ?? 0;
  const endpoints = endpointsData?.endpoints ?? [];
  const providers = useMemo(() => extractProviders(models), [models]);

  const filteredModels = useMemo(
    () =>
      state.selectedProviders.size > 0
        ? models.filter((m) => state.selectedProviders.has(m.id.split("/")[0]))
        : models,
    [models, state.selectedProviders],
  );

  const selectedModels = useMemo(
    () => filteredModels.filter((m) => state.selectedModelIds.has(m.id)),
    [filteredModels, state.selectedModelIds],
  );

  const searchRef = useRef<HTMLInputElement>(null);

  const hasActiveFilters = useMemo(
    () =>
      Boolean(
        filters.search ||
          filters.free ||
          filters.maxPrice != null ||
          filters.minContext != null ||
          filters.modality ||
          state.selectedProviders.size > 0,
      ),
    [filters, state.selectedProviders],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters({ search: state.searchTerm || undefined });
    }, 300);
    return () => clearTimeout(timer);
  }, [state.searchTerm, setFilters]);

  const [trackedFilters, setTrackedFilters] = useState({
    filters,
    selectedProviders: state.selectedProviders,
  });
  if (
    trackedFilters.filters !== filters ||
    trackedFilters.selectedProviders !== state.selectedProviders
  ) {
    setTrackedFilters({ filters, selectedProviders: state.selectedProviders });
    dispatch({ type: "RESET_CARD_LIMIT" });
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (state.showHint) dispatch({ type: "DISMISS_HINT" });
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
  }, [clearSelection, state.showHint, dispatch]);

  const handleRowClick = useCallback(
    (model: Model) => toggleRow(model.id),
    [toggleRow],
  );

  const handleSelectAll = useCallback(
    (ids: string[]) => selectAll(ids),
    [selectAll],
  );

  const handleNameClick = useCallback(
    (model: Model) => openDetail(model.id),
    [openDetail],
  );

  const clearAllFilters = useCallback(() => {
    setFilters({
      search: undefined,
      free: undefined,
      maxPrice: undefined,
      minContext: undefined,
      modality: undefined,
    });
    dispatch({ type: "CLEAR_ALL_FILTERS" });
  }, [setFilters, dispatch]);

  const maxCtx = useMemo(
    () => filteredModels.reduce((max, m) => Math.max(max, m.context_length), 1),
    [filteredModels],
  );

  return (
    <>
      <AmbientBackground />
      <CursorGlow />
      <AnimatePresence mode="wait">
        {isLoading ? (
          <ModelsLoadingSkeleton />
        ) : (
          <m.div
            key="content"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="px-sp-6 py-sp-8 max-w-[1800px] mx-auto relative z-[1]"
          >
            <ModelsHeader
              hasActiveFilters={hasActiveFilters}
              onOpenMobileFilters={() =>
                dispatch({ type: "SET_MOBILE_FILTERS", open: true })
              }
            />

            <div className="flex gap-sp-6 min-h-[calc(100svh-180px)]">
              <ModelsFilterSidebar
                searchRef={searchRef}
                searchTerm={state.searchTerm}
                onSearchChange={(term) =>
                  dispatch({ type: "SET_SEARCH_TERM", term })
                }
                showHint={state.showHint}
                filters={filters}
                setFilters={setFilters}
                providers={providers}
                selectedProviders={state.selectedProviders}
                onProviderChange={(p) =>
                  dispatch({ type: "SET_PROVIDERS", providers: p })
                }
                total={total}
                hasActiveFilters={hasActiveFilters}
                onClearAll={clearAllFilters}
              />

              <div className="flex-1 min-w-0">
                <FadeIn delay={2}>
                  <ModelsToolbar
                    selectedModels={selectedModels}
                    viewMode={state.viewMode}
                    onSetViewMode={(mode) =>
                      dispatch({ type: "SET_VIEW_MODE", mode })
                    }
                    onClearSelection={clearSelection}
                    onSaveGroup={() => {
                      if (selectedModels.length > 0) {
                        createGroup.mutate({
                          name: `Group ${Date.now()}`,
                          description: `${selectedModels.length} models`,
                        });
                      }
                    }}
                  />

                  <AnimatePresence mode="wait">
                    {state.viewMode === "table" ? (
                      <m.div
                        key="table"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <ModelsTable
                          models={filteredModels}
                          selectedModelIds={state.selectedModelIds}
                          onRowClick={handleRowClick}
                          onSelectAll={handleSelectAll}
                          onNameClick={handleNameClick}
                          scrollClassName="max-h-[calc(100svh-260px)]"
                        />
                      </m.div>
                    ) : (
                      <m.div
                        key="cards"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <ModelsCardView
                          models={filteredModels}
                          maxContext={maxCtx}
                          cardLimit={state.cardLimit}
                          onCardClick={(id) => openDetail(id)}
                          onLoadMore={() =>
                            dispatch({ type: "LOAD_MORE_CARDS" })
                          }
                        />
                      </m.div>
                    )}
                  </AnimatePresence>

                  {filteredModels.length === 0 && !isLoading && (
                    <div className="text-center py-sp-16">
                      <Cpu className="h-12 w-12 text-brand-mist mx-auto mb-sp-4" />
                      <p className="text-h5 text-brand-charcoal mb-sp-2">
                        No models match your filters
                      </p>
                      <p className="text-body-sm text-brand-slate mb-sp-6">
                        Try adjusting your search or filter criteria.
                      </p>
                      {hasActiveFilters && (
                        <Button variant="secondary" onClick={clearAllFilters}>
                          Reset all filters
                        </Button>
                      )}
                    </div>
                  )}
                </FadeIn>
              </div>
            </div>
          </m.div>
        )}
      </AnimatePresence>

      <ModelDetailPanel
        selectedModelId={state.selectedModelId}
        modelDetail={modelDetail}
        endpoints={endpoints}
        panelTab={state.panelTab}
        onTabChange={(tab) => dispatch({ type: "SET_PANEL_TAB", tab })}
        onClose={closeDetail}
      />

      <SlideOutPanel
        open={state.showMobileFilters}
        onClose={() => dispatch({ type: "SET_MOBILE_FILTERS", open: false })}
        title="Filters"
        width="md"
      >
        <FilterContent
          filters={filters}
          setFilters={setFilters}
          providers={providers}
          selectedProviders={state.selectedProviders}
          onProviderChange={(p) =>
            dispatch({ type: "SET_PROVIDERS", providers: p })
          }
        />
        {hasActiveFilters && (
          <Button
            variant="secondary"
            size="sm"
            className="mt-sp-4 w-full"
            onClick={() => {
              clearAllFilters();
              dispatch({ type: "SET_MOBILE_FILTERS", open: false });
            }}
          >
            Clear all filters
          </Button>
        )}
      </SlideOutPanel>

      <AnimatePresence>
        {selectedModels.length >= 2 && selectedModels.length <= 3 && (
          <ComparisonTray models={selectedModels} onClose={clearSelection} />
        )}
      </AnimatePresence>
    </>
  );
}
