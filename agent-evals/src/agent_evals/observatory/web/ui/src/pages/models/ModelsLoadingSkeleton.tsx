import { m } from "framer-motion";
import { Skeleton } from "../../components/Skeleton";

export function ModelsLoadingSkeleton() {
  return (
    <m.div
      key="skeleton"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="px-sp-6 py-sp-8 max-w-[1800px] mx-auto relative z-[1]"
    >
      <div className="flex items-center gap-sp-3 mb-sp-8">
        <Skeleton variant="circle" className="h-8 w-8" />
        <Skeleton variant="text" className="h-8 w-32" />
      </div>

      <div className="flex gap-sp-6">
        <div className="hidden lg:block w-[264px] shrink-0 space-y-sp-6">
          <Skeleton variant="text" className="h-10 w-full rounded-card" />
          <div className="space-y-sp-2">
            <Skeleton variant="text" className="h-5 w-20" />
            <Skeleton variant="text" className="h-4 w-36" />
            <Skeleton variant="text" className="h-4 w-full" />
            <Skeleton variant="text" className="h-4 w-44" />
          </div>
          <div className="space-y-sp-2">
            <Skeleton variant="text" className="h-5 w-28" />
            <Skeleton variant="text" className="h-4 w-full" />
            <Skeleton variant="text" className="h-4 w-32" />
          </div>
          <div className="space-y-sp-2">
            <Skeleton variant="text" className="h-5 w-20" />
            <Skeleton variant="text" className="h-4 w-28" />
            <Skeleton variant="text" className="h-4 w-36" />
            <Skeleton variant="text" className="h-4 w-32" />
          </div>
          <Skeleton variant="text" className="h-4 w-24 mt-sp-4" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-sp-6">
            <div className="flex items-center gap-sp-3">
              <Skeleton variant="text" className="h-9 w-28 rounded-card" />
              <Skeleton variant="text" className="h-9 w-32 rounded-card" />
            </div>
            <div className="flex items-center gap-sp-1">
              <Skeleton variant="text" className="h-9 w-9 rounded-card" />
              <Skeleton variant="text" className="h-9 w-9 rounded-card" />
            </div>
          </div>
          <div className="flex items-center gap-sp-3 border-b border-brand-mist pb-sp-3 mb-sp-2">
            <Skeleton variant="text" className="h-4 w-[40%]" />
            <Skeleton variant="text" className="h-4 w-[15%]" />
            <Skeleton variant="text" className="h-4 w-[15%]" />
            <Skeleton variant="text" className="h-4 w-[10%]" />
            <Skeleton variant="text" className="h-4 w-[10%]" />
            <Skeleton variant="text" className="h-4 w-[10%]" />
          </div>
          <div className="space-y-sp-1">
            {Array.from({ length: 8 }).map((_, index) => (
              <m.div
                key={index}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex items-center gap-sp-3 py-sp-3 border-b border-brand-mist/50"
              >
                <Skeleton variant="text" className="h-5 w-[40%]" />
                <Skeleton variant="text" className="h-5 w-[15%]" />
                <Skeleton variant="text" className="h-5 w-[15%]" />
                <Skeleton variant="text" className="h-5 w-[10%]" />
                <Skeleton variant="text" className="h-5 w-[10%]" />
                <Skeleton variant="text" className="h-5 w-[10%]" />
              </m.div>
            ))}
          </div>
        </div>
      </div>
    </m.div>
  );
}
