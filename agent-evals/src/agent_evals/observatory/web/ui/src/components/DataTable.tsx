import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronUp, ChevronDown } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";
import { CompassCheckbox } from "./CompassCheckbox";

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  selectedRowIds?: Set<string>;
  getRowId?: (row: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  selectedRowIds,
  getRowId,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  return (
    <div className="overflow-x-auto rounded-card border border-brand-mist">
      <table className="w-full text-body-sm">
        <thead className="bg-brand-cream">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {selectedRowIds && <th className="w-10" />}
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
                    {header.column.getCanSort() && (
                      header.column.getIsSorted() === "asc" ? (
                        <ChevronUp className="h-4 w-4 text-brand-goldenrod" />
                      ) : header.column.getIsSorted() === "desc" ? (
                        <ChevronDown className="h-4 w-4 text-brand-goldenrod" />
                      ) : (
                        <ArrowUpDown className="h-4 w-4 text-brand-slate/50" />
                      )
                    )}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const rowId = getRowId?.(row.original) ?? row.id;
            const isSelected = selectedRowIds?.has(rowId) ?? false;

            return (
              <tr
                key={row.id}
                className={cn(
                  "border-t border-brand-mist transition-colors duration-micro",
                  "hover:bg-brand-cream/50",
                  onRowClick && "cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
                  isSelected && "bg-brand-goldenrod/10",
                )}
                onClick={() => onRowClick?.(row.original)}
              >
                {selectedRowIds && (
                  <td className="px-sp-2 py-sp-3 w-10">
                    {isSelected && (
                      <CompassCheckbox
                        checked
                        aria-label={`Selected`}
                      />
                    )}
                  </td>
                )}
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
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
