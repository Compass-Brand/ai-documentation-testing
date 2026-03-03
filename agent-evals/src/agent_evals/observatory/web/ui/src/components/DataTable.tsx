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
import { ArrowUpDown, ChevronUp, ChevronDown } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "../lib/utils";
import { CompassCheckbox } from "./CompassCheckbox";

const VIRTUAL_THRESHOLD = 50;

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

  const renderRow = (row: Row<T>) => {
    const rowId = getRowId?.(row.original) ?? row.id;
    const isSelected = selectedRowIds?.has(rowId) ?? false;

    return (
      <tr
        key={row.id}
        className={cn(
          "border-t border-brand-mist transition-colors duration-micro",
          "hover:bg-brand-cream/50",
          onRowClick &&
            "cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
          isSelected && "bg-brand-goldenrod/10",
        )}
        onClick={() => onRowClick?.(row.original)}
      >
        {selectedRowIds && (
          <td className="px-sp-2 py-sp-3 w-10">
            <CompassCheckbox
              checked={isSelected}
              aria-label="Select row"
            />
          </td>
        )}
        {row.getVisibleCells().map((cell) => (
          <td
            key={cell.id}
            className="px-sp-4 py-sp-3 text-brand-charcoal"
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </tr>
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
          return renderRow(row);
        })}
        {bottomPad > 0 && (
          <tr>
            <td colSpan={colSpan} style={{ height: `${bottomPad}px` }} />
          </tr>
        )}
      </>
    );
  };

  return (
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
            : rows.map((row) => renderRow(row))}
        </tbody>
      </table>
    </div>
  );
}
