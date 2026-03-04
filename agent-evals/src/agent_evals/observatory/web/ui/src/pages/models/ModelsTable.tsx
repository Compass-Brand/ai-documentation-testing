import { useState, useMemo } from "react";
import { Copy, Check } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import type { Model } from "../../api/client";
import { DataTable } from "../../components/DataTable";
import { Tooltip } from "../../components/Tooltip";
import { formatPrice, formatDeployed } from "./models-utils";

function CopyModelIdButton({ modelId }: { modelId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const orId = modelId.startsWith("openrouter/")
      ? modelId
      : `openrouter/${modelId}`;
    navigator.clipboard.writeText(orId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Tooltip content={copied ? "Copied!" : "Copy OpenRouter model ID"}>
      <button
        className="relative h-3.5 w-3.5 text-brand-slate hover:text-brand-charcoal transition-colors duration-micro ml-sp-2"
        onClick={handleCopy}
        aria-label="Copy model ID"
      >
        <span
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-150 ${copied ? "opacity-0" : "opacity-100"}`}
        >
          <Copy className="h-3.5 w-3.5" />
        </span>
        <span
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-150 ${copied ? "opacity-100" : "opacity-0"}`}
        >
          <Check className="h-3.5 w-3.5 text-brand-sage" />
        </span>
      </button>
    </Tooltip>
  );
}

function ModelNameCell({
  model,
  onNameClick,
}: {
  model: Model;
  onNameClick: (model: Model) => void;
}) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onNameClick(model);
  };

  return (
    <span className="inline-flex items-center min-w-0 max-w-full">
      <button
        className="text-brand-goldenrod cursor-pointer hover:underline font-medium truncate"
        onClick={handleClick}
        title={model.name}
      >
        {model.name}
      </button>
      <CopyModelIdButton modelId={model.id} />
    </span>
  );
}

interface ModelsTableProps {
  models: Model[];
  selectedModelIds: Set<string>;
  onRowClick: (model: Model) => void;
  onSelectAll: (ids: string[]) => void;
  onNameClick: (model: Model) => void;
  scrollClassName?: string;
}

export function ModelsTable({
  models,
  selectedModelIds,
  onRowClick,
  onSelectAll,
  onNameClick,
  scrollClassName,
}: ModelsTableProps) {
  const columns: ColumnDef<Model>[] = useMemo(
    () => [
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => (
          <ModelNameCell model={row.original} onNameClick={onNameClick} />
        ),
      },
      {
        accessorKey: "prompt_price",
        header: () => (
          <Tooltip content="Cost per million prompt (input) tokens">
            <span className="cursor-help">Prompt $/M</span>
          </Tooltip>
        ),
        cell: ({ getValue }) => formatPrice(getValue<number>()),
        meta: { align: "right", width: "11%" },
      },
      {
        accessorKey: "completion_price",
        header: () => (
          <Tooltip content="Cost per million completion (output) tokens">
            <span className="cursor-help">Completion $/M</span>
          </Tooltip>
        ),
        cell: ({ getValue }) => formatPrice(getValue<number>()),
        meta: { align: "right", width: "13%" },
      },
      {
        accessorKey: "context_length",
        header: "Context",
        cell: ({ getValue }) =>
          `${(getValue<number>() / 1000).toFixed(0)}k`,
        meta: { align: "right", width: "9%" },
      },
      {
        accessorKey: "modality",
        header: "Modality",
        meta: { width: "9%" },
      },
      {
        accessorKey: "tokenizer",
        header: "Tokenizer",
        cell: ({ getValue }) => getValue<string>() || "\u2014",
        meta: { width: "10%" },
      },
      {
        accessorKey: "created",
        header: "Deployed",
        cell: ({ getValue }) => formatDeployed(getValue<number>()),
        meta: { align: "right", width: "11%" },
      },
    ],
    [onNameClick],
  );

  return (
    <DataTable
      columns={columns}
      data={models}
      selectedRowIds={selectedModelIds}
      getRowId={(model) => model.id}
      onRowClick={onRowClick}
      onSelectAll={onSelectAll}
      scrollClassName={scrollClassName}
    />
  );
}
