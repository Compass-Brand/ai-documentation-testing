import {
  LayoutGrid,
  LayoutList,
  Play,
  Save,
  X,
} from "lucide-react";
import type { Model } from "../../api/client";
import { Button } from "../../components/Button";
import { cn } from "../../lib/utils";
import type { ViewMode } from "./useModelsReducer";

interface ModelsToolbarProps {
  selectedModels: Model[];
  viewMode: ViewMode;
  onSetViewMode: (mode: ViewMode) => void;
  onClearSelection: () => void;
  onSaveGroup: () => void;
}

export function ModelsToolbar({
  selectedModels,
  viewMode,
  onSetViewMode,
  onClearSelection,
  onSaveGroup,
}: ModelsToolbarProps) {
  return (
    <div className="flex items-center justify-between mb-sp-6">
      <div className="flex items-center gap-sp-3">
        {selectedModels.length > 0 && (
          <>
            <span className="text-body-sm text-brand-slate">
              {selectedModels.length} selected
            </span>
            <Button variant="secondary" size="sm" onClick={onClearSelection}>
              <X className="h-4 w-4 mr-sp-1" />
              Clear
            </Button>
          </>
        )}
        <Button
          variant="primary"
          size="sm"
          disabled={selectedModels.length === 0}
        >
          <Play className="h-4 w-4 mr-sp-2" />
          Run Selected
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={selectedModels.length === 0}
          onClick={onSaveGroup}
        >
          <Save className="h-4 w-4 mr-sp-2" />
          Save as Group
        </Button>
      </div>
      <div className="flex items-center gap-sp-1">
        <button
          aria-label="Table view"
          className={cn(
            "rounded-card p-sp-2 transition-colors duration-micro",
            viewMode === "table"
              ? "bg-brand-goldenrod/10 text-brand-goldenrod"
              : "text-brand-slate hover:text-brand-charcoal",
          )}
          onClick={() => onSetViewMode("table")}
        >
          <LayoutList className="h-5 w-5" />
        </button>
        <button
          aria-label="Card view"
          className={cn(
            "rounded-card p-sp-2 transition-colors duration-micro",
            viewMode === "cards"
              ? "bg-brand-goldenrod/10 text-brand-goldenrod"
              : "text-brand-slate hover:text-brand-charcoal",
          )}
          onClick={() => onSetViewMode("cards")}
        >
          <LayoutGrid className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
