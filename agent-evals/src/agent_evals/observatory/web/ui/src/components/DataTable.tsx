import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
  type Row,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { motion } from "framer-motion";
import { ArrowUpDown, ChevronUp, ChevronDown } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { cn } from "../lib/utils";
import { CompassCheckbox } from "./CompassCheckbox";
import { CustomScrollbar } from "./CustomScrollbar";

const VIRTUAL_THRESHOLD = 50;

const ROW_SPRING = { type: "spring" as const, stiffness: 400, damping: 30 };

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  selectedRowIds?: Set<string>;
  getRowId?: (row: T) => string;
  onSelectAll?: (allIds: string[]) => void;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  selectedRowIds,
  getRowId,
  onSelectAll,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  const rows = table.getRowModel().rows;
  const useVirtual = rows.length > VIRTUAL_THRESHOLD;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 48,
    overscan: 10,
    enabled: useVirtual,
  });

  const colSpan = columns.length + (selectedRowIds ? 1 : 0);

  const selectedPositions = useMemo(() => {
    if (!selectedRowIds || !getRowId || rows.length === 0) return [];
    return rows.reduce<number[]>((acc, row, index) => {
      if (selectedRowIds.has(getRowId(row.original))) {
        acc.push(index / rows.length);
      }
      return acc;
    }, []);
  }, [selectedRowIds, getRowId, rows]);

  const renderRow = (row: Row<T>, rowIndex: number) => {
    const rowId = getRowId?.(row.original) ?? row.id;
    const isSelected = selectedRowIds?.has(rowId) ?? false;

    return (
      <motion.tr
        key={row.id}
        layout
        className={cn(
          "border-t border-brand-mist transition-colors duration-micro",
          rowIndex % 2 === 1 ? "bg-brand-cream/20" : "bg-white",
          onRowClick &&
            "cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
          isSelected && "bg-brand-goldenrod/10",
        )}
        style={{
          borderLeft: isSelected ? "3px solid #C2A676" : "3px solid transparent",
        }}
        whileHover={{ y: -1, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
        transition={ROW_SPRING}
        onClick={() => onRowClick?.(row.original)}
      >
        {selectedRowIds && (
          <td className="py-sp-3 overflow-hidden">
            <motion.div
              initial={false}
              animate={{
                width: isSelected ? 40 : 0,
                opacity: isSelected ? 1 : 0,
                x: isSelected ? 0 : -20,
              }}
              transition={ROW_SPRING}
              className="flex items-center justify-center overflow-hidden"
            >
              <CompassCheckbox
                checked={isSelected}
                aria-label="Select row"
              />
            </motion.div>
          </td>
        )}
        {row.getVisibleCells().map((cell) => (
          <td
            key={cell.id}
            className={cn(
              "px-sp-4 py-sp-3 text-brand-charcoal",
              (cell.column.columnDef.meta as { align?: string })?.align === "right" && "text-right tabular-nums",
            )}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </motion.tr>
    );
  };

  const renderHeader = () =>
    table.getHeaderGroups().map((hg) => (
      <tr key={hg.id}>
        {selectedRowIds && (
          <th className="w-10 px-sp-2">
            <CompassCheckbox
              checked={selectedRowIds.size > 0 && selectedRowIds.size === data.length}
              onChange={(checked) => {
                if (checked && getRowId) {
                  onSelectAll?.(data.map(getRowId));
                } else {
                  onSelectAll?.([]);
                }
              }}
              aria-label="Select all"
            />
          </th>
        )}
        {hg.headers.map((header) => (
          <th
            key={header.id}
            className={cn(
              "px-sp-4 py-sp-3 text-left font-medium text-brand-slate",
              "border-l-2 border-transparent",
              header.column.getCanSort() &&
                "cursor-pointer select-none hover:border-l-2 hover:border-brand-goldenrod",
              (header.column.columnDef.meta as { align?: string })?.align === "right" && "text-right",
            )}
            onClick={header.column.getToggleSortingHandler()}
          >
            <span className="inline-flex items-center gap-sp-2">
              {flexRender(
                header.column.columnDef.header,
                header.getContext(),
              )}
              {header.column.getCanSort() &&
                (header.column.getIsSorted() === "asc" ? (
                  <ChevronUp className="h-4 w-4 text-brand-goldenrod" />
                ) : header.column.getIsSorted() === "desc" ? (
                  <ChevronDown className="h-4 w-4 text-brand-goldenrod" />
                ) : (
                  <ArrowUpDown className="h-4 w-4 text-brand-slate/50" />
                ))}
            </span>
          </th>
        ))}
      </tr>
    ));

  const renderVirtualBody = () => {
    const virtualItems = virtualizer.getVirtualItems();
    const topPad = virtualItems.length > 0 ? virtualItems[0].start : 0;
    const bottomPad =
      virtualItems.length > 0
        ? virtualizer.getTotalSize() -
          (virtualItems[virtualItems.length - 1]?.end ?? 0)
        : 0;

    return (
      <>
        {topPad > 0 && (
          <tr>
            <td colSpan={colSpan} style={{ height: `${topPad}px` }} />
          </tr>
        )}
        {virtualItems.map((virtualRow) => {
          const row = rows[virtualRow.index];
          return renderRow(row, virtualRow.index);
        })}
        {bottomPad > 0 && (
          <tr>
            <td colSpan={colSpan} style={{ height: `${bottomPad}px` }} />
          </tr>
        )}
      </>
    );
  };

  const tableContent = (
    <div
      ref={useVirtual ? scrollContainerRef : undefined}
      className={cn(
        "overflow-x-auto rounded-card border border-brand-mist",
        useVirtual && "max-h-[600px] overflow-y-auto",
      )}
      {...(useVirtual ? { "data-virtual-scroller": "" } : {})}
    >
      <table className="w-full text-body-sm">
        <thead
          className={cn(
            "bg-brand-cream",
            useVirtual && "sticky top-0 z-10",
          )}
        >
          {renderHeader()}
        </thead>
        <tbody>
          {useVirtual
            ? renderVirtualBody()
            : rows.map((row, index) => renderRow(row, index))}
        </tbody>
      </table>
    </div>
  );

  if (useVirtual) {
    return (
      <CustomScrollbar
        scrollRef={scrollContainerRef as React.RefObject<HTMLDivElement>}
        selectedPositions={selectedPositions}
      >
        {tableContent}
      </CustomScrollbar>
    );
  }

  return tableContent;
}
