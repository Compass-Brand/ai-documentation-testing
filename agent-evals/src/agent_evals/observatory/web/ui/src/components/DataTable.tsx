import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  onSelectionChange?: (selected: T[]) => void;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  selectable,
  onSelectionChange,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [rowSelection, setRowSelection] = useState({});

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    onRowSelectionChange: (updater) => {
      setRowSelection(updater);
      if (onSelectionChange) {
        const next =
          typeof updater === "function" ? updater(rowSelection) : updater;
        const selected = Object.keys(next)
          .filter((k) => next[k as keyof typeof next])
          .map((k) => data[parseInt(k)]);
        onSelectionChange(selected);
      }
    },
    enableRowSelection: selectable,
    state: { sorting, rowSelection },
  });

  return (
    <div className="overflow-x-auto rounded-card border border-brand-mist">
      <table className="w-full text-body-sm">
        <thead className="bg-brand-cream">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className={cn(
                    "px-sp-4 py-sp-3 text-left font-medium text-brand-slate",
                    header.column.getCanSort() &&
                      "cursor-pointer select-none",
                  )}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  <span className="inline-flex items-center gap-sp-2">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                    {header.column.getCanSort() && (
                      <ArrowUpDown className="h-4 w-4 text-brand-slate/50" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={cn(
                "border-t border-brand-mist transition-colors duration-micro",
                "hover:bg-brand-cream/50",
                onRowClick && "cursor-pointer",
                row.getIsSelected() && "bg-brand-goldenrod/10",
              )}
              onClick={() => onRowClick?.(row.original)}
            >
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
          ))}
        </tbody>
      </table>
    </div>
  );
}
