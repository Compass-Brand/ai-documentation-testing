import { Cpu, Filter } from "lucide-react";
import { FadeIn } from "../../components/FadeIn";
import { Button } from "../../components/Button";

interface ModelsHeaderProps {
  hasActiveFilters: boolean;
  onOpenMobileFilters: () => void;
}

export function ModelsHeader({
  hasActiveFilters,
  onOpenMobileFilters,
}: ModelsHeaderProps) {
  return (
    <>
      <FadeIn>
        <h1 className="text-h2 text-brand-charcoal inline-flex items-center gap-sp-3 mb-sp-8">
          <Cpu className="h-8 w-8 text-brand-goldenrod" />
          Models
        </h1>
      </FadeIn>

      <div className="lg:hidden mb-sp-4 flex items-center gap-sp-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={onOpenMobileFilters}
        >
          <Filter className="h-4 w-4 mr-sp-1" />
          Filters
          {hasActiveFilters && (
            <span className="ml-sp-1 bg-brand-goldenrod text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
              !
            </span>
          )}
        </Button>
      </div>
    </>
  );
}
