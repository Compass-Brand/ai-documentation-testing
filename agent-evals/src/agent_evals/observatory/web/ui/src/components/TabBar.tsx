import { useRef, useState, useEffect, useCallback } from "react";
import { cn } from "../lib/utils";

interface Tab {
  key: string;
  label: string;
}

interface TabBarProps {
  tabs: Tab[];
  activeKey: string;
  onTabChange: (key: string) => void;
}

export function TabBar({ tabs, activeKey, onTabChange }: TabBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const [indicator, setIndicator] = useState({ left: 0, width: 0 });

  const updateIndicator = useCallback(() => {
    const activeEl = tabRefs.current.get(activeKey);
    const container = containerRef.current;
    if (activeEl && container) {
      const containerRect = container.getBoundingClientRect();
      const tabRect = activeEl.getBoundingClientRect();
      setIndicator({
        left: tabRect.left - containerRect.left,
        width: tabRect.width,
      });
    }
  }, [activeKey]);

  useEffect(() => {
    updateIndicator();
  }, [updateIndicator]);

  return (
    <div
      ref={containerRef}
      className="relative flex gap-sp-2 border-b border-brand-mist"
      role="tablist"
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          ref={(el) => {
            if (el) tabRefs.current.set(tab.key, el);
          }}
          role="tab"
          aria-selected={activeKey === tab.key}
          onClick={() => onTabChange(tab.key)}
          className={cn(
            "px-sp-4 py-sp-2 text-body-sm font-medium transition-colors duration-micro",
            activeKey === tab.key
              ? "text-brand-goldenrod"
              : "text-brand-slate hover:text-brand-charcoal",
          )}
        >
          {tab.label}
        </button>
      ))}
      <div
        className="absolute bottom-0 h-0.5 bg-brand-goldenrod transition-all duration-state"
        style={{ left: indicator.left, width: indicator.width }}
      />
    </div>
  );
}
