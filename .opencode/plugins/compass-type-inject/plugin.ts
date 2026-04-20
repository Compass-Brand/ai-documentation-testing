import * as path from "node:path";
import { existsSync } from "node:fs";
import {
  CHARS_PER_TOKEN,
  type Config,
  ContentFormatter,
  defaultConfig,
  type ExtractedTypeKind,
  filterVisibleTypes,
  findNearestTsconfig,
  formatDiagnostics,
  getProjectDiagnostics,
  isBarrelFile,
  prioritizeTypes,
  TypeExtractor,
  TypeLookup,
} from "@nick-vi/type-inject-core";
import { type Plugin, tool } from "@opencode-ai/plugin";

const TYPE_KINDS = [
  "function",
  "type",
  "interface",
  "enum",
  "class",
  "const",
] as const;

type ToolReadContext = {
  filePath: string;
  offset?: number;
  limit?: number;
};

function isTypeScriptLikeFile(filePath: string): boolean {
  return (
    filePath.endsWith(".ts") ||
    filePath.endsWith(".tsx") ||
    filePath.endsWith(".mts") ||
    filePath.endsWith(".cts") ||
    filePath.endsWith(".svelte")
  );
}

function toAbsolutePath(directory: string, filePath: string): string {
  return path.isAbsolute(filePath) ? filePath : path.resolve(directory, filePath);
}

function getRootTsconfigPath(directory: string): string | null {
  const tsconfigPath = path.join(directory, "tsconfig.json");
  return existsSync(tsconfigPath) ? tsconfigPath : null;
}

function getScopedTsconfigPath(directory: string, filePath?: string): string | null {
  if (filePath) {
    return findNearestTsconfig(filePath, directory);
  }

  return getRootTsconfigPath(directory);
}

function buildTypeKindSchema() {
  return tool.schema.array(
    tool.schema.enum([
      TYPE_KINDS[0],
      TYPE_KINDS[1],
      TYPE_KINDS[2],
      TYPE_KINDS[3],
      TYPE_KINDS[4],
      TYPE_KINDS[5],
    ]),
  );
}

export const CompassTypeInjectPlugin: Plugin = async ({ directory }) => {
  const config: Config = { ...defaultConfig };
  const extractor = new TypeExtractor(directory, config);
  const formatter = new ContentFormatter(config);
  const lookupCache = new Map<string, TypeLookup>();
  const currentReads = new Map<string, ToolReadContext>();
  const currentWrites = new Map<string, { filePath: string }>();

  function getLookup(filePath?: string): { lookup: TypeLookup; tsconfigPath: string } | null {
    const tsconfigPath = getScopedTsconfigPath(directory, filePath);
    if (!tsconfigPath) return null;

    const lookupRoot = path.dirname(tsconfigPath);
    let lookup = lookupCache.get(lookupRoot);
    if (!lookup) {
      lookup = new TypeLookup(lookupRoot, config);
      lookupCache.set(lookupRoot, lookup);
    }

    return { lookup, tsconfigPath };
  }

  function appendDiagnosticsToOutput(output: { output?: unknown }, diagnostics: string): void {
    if (typeof output.output !== "string") return;
    output.output = `${output.output}\n\nTypeScript diagnostics detected after write:\n\n${diagnostics}`;
  }

  return {
    tool: {
      ts_lookup_type: tool({
        description:
          "Look up TypeScript type definitions by name. Optionally scope the search with a file path when working in a nested package.",
        args: {
          name: tool.schema
            .string()
            .describe("Type name to search for (for example: User, Config, getUser)"),
          exact: tool.schema
            .boolean()
            .optional()
            .describe("Exact match when true, contains match when false. Default: true"),
          kind: buildTypeKindSchema()
            .optional()
            .describe("Optional filter for type kinds"),
          includeUsages: tool.schema
            .boolean()
            .optional()
            .describe("Include importing files when true. Default: false"),
          limit: tool.schema
            .number()
            .optional()
            .describe("Maximum results to return. Default: 5"),
          scopeFile: tool.schema
            .string()
            .optional()
            .describe("Optional file path used to find the nearest tsconfig.json for nested packages"),
        },
        async execute(args) {
          const scoped = getLookup(args.scopeFile);
          if (!scoped) {
            return args.scopeFile
              ? `No tsconfig.json found near ${args.scopeFile}`
              : "No repo-root tsconfig.json found. Provide scopeFile when working in a nested TypeScript package.";
          }

          const result = scoped.lookup.findType(args.name, {
            exact: args.exact ?? true,
            kind: args.kind as ExtractedTypeKind[] | undefined,
            includeUsages: args.includeUsages ?? false,
            limit: args.limit ?? 5,
          });

          if (!result.found) {
            return `No types found matching "${args.name}"`;
          }

          const lines: string[] = [];
          lines.push(
            `Found ${result.totalMatches} type(s) matching "${args.name}" (showing ${result.types.length}):`,
          );
          lines.push("");

          for (const type of result.types) {
            const offset = type.line - 1;
            const limit = type.lineEnd - type.line + 1;
            lines.push(`## ${type.name} (${type.kind})`);
            lines.push(`File: ${type.relativePath} [offset=${offset},limit=${limit}]`);
            if (type.exported) lines.push("Exported: yes");
            if (type.jsdoc) lines.push(`JSDoc: ${type.jsdoc}`);
            if (type.generics?.length) lines.push(`Generics: <${type.generics.join(", ")}>`);
            lines.push("");
            lines.push("```typescript");
            lines.push(type.signature);
            lines.push("```");

            if (type.usedIn?.length) {
              lines.push("");
              lines.push(`Used in ${type.usedIn.length} file(s):`);
              for (const usage of type.usedIn.slice(0, 10)) {
                lines.push(`  - ${usage.relativePath}:${usage.line}`);
              }
              if (type.usedIn.length > 10) {
                lines.push(`  ... and ${type.usedIn.length - 10} more`);
              }
            }

            lines.push("");
          }

          if (result.totalMatches > result.types.length) {
            lines.push(`(${result.totalMatches - result.types.length} more results not shown)`);
          }

          lines.push(`Search time: ${result.searchTimeMs}ms`);
          if (result.indexBuilt) {
            lines.push("(Index was built during this query)");
          }

          return lines.join("\n");
        },
      }),

      ts_list_types: tool({
        description:
          "List TypeScript type names in the current project or nested package. Provide scopeFile when the repo root does not own the active tsconfig.json.",
        args: {
          kind: buildTypeKindSchema()
            .optional()
            .describe("Optional filter for type kinds"),
          limit: tool.schema
            .number()
            .optional()
            .describe("Maximum results to return. Default: 100"),
          scopeFile: tool.schema
            .string()
            .optional()
            .describe("Optional file path used to find the nearest tsconfig.json for nested packages"),
        },
        async execute(args) {
          const scoped = getLookup(args.scopeFile);
          if (!scoped) {
            return args.scopeFile
              ? `No tsconfig.json found near ${args.scopeFile}`
              : "No repo-root tsconfig.json found. Provide scopeFile when working in a nested TypeScript package.";
          }

          const results = scoped.lookup.listTypeNames({
            kind: args.kind as ExtractedTypeKind[] | undefined,
            limit: args.limit ?? 100,
          });

          if (results.length === 0) {
            return "No types found in the project";
          }

          const stats = scoped.lookup.getStats();
          return [
            `Found ${stats.totalTypes} types in ${stats.totalFiles} files. Showing ${results.length}:`,
            "",
            results.map((item) => `${item.name} (${item.kind})`).join(", "),
          ].join("\n");
        },
      }),

      ts_type_check: tool({
        description:
          "Run TypeScript type checking for the project or for a file scoped to the nearest tsconfig.json.",
        args: {
          file: tool.schema
            .string()
            .optional()
            .describe("Optional file path to scope the check to the nearest tsconfig.json"),
        },
        async execute(args) {
          const tsconfigPath = getScopedTsconfigPath(directory, args.file);
          if (!tsconfigPath) {
            return args.file
              ? `No tsconfig.json found near ${args.file}`
              : "No repo-root tsconfig.json found. Provide file when working in a nested TypeScript package.";
          }

          const absoluteFilePath = args.file ? toAbsolutePath(directory, args.file) : undefined;
          const result = getProjectDiagnostics(tsconfigPath, absoluteFilePath);

          if (result.success) {
            return absoluteFilePath
              ? `No TypeScript errors found in ${args.file}`
              : "No TypeScript errors found in the project";
          }

          const formatted = formatDiagnostics(
            result.diagnostics,
            path.dirname(tsconfigPath),
            absoluteFilePath
              ? { modifiedFile: absoluteFilePath, maxFileErrors: 50, maxProjectFiles: 20 }
              : { maxProjectFiles: 20 },
          );

          const header = absoluteFilePath
            ? `TypeScript errors found in ${args.file}:`
            : `TypeScript errors found in project (${result.diagnostics.length} total):`;

          return `${header}\n\n${formatted}`;
        },
      }),
    },

    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && typeof output.args?.filePath === "string") {
        currentReads.set(input.callID, {
          filePath: output.args.filePath,
          offset: typeof output.args.offset === "number" ? output.args.offset : undefined,
          limit: typeof output.args.limit === "number" ? output.args.limit : undefined,
        });
      }

      if (input.tool === "write" && typeof output.args?.filePath === "string") {
        currentWrites.set(input.callID, { filePath: output.args.filePath });
      }
    },

    "tool.execute.after": async (input, output) => {
      if (input.tool === "read") {
        const readContext = currentReads.get(input.callID);
        currentReads.delete(input.callID);

        if (!readContext) return;
        if (!isTypeScriptLikeFile(readContext.filePath)) return;
        if (typeof output.output !== "string") return;

        try {
          const originalContent = output.output;
          if (config.budget.skipBarrelFiles && isBarrelFile(originalContent)) {
            return;
          }

          const lineRange =
            readContext.offset !== undefined && readContext.limit !== undefined
              ? { offset: readContext.offset, limit: readContext.limit }
              : undefined;

          const types = extractor.extract(readContext.filePath, lineRange);
          const prioritized = prioritizeTypes(types, {
            tokenBudget: config.budget.maxTokens,
            debug: config.debug,
          });
          const totalLines = originalContent.split("\n").length;
          const visibleTypes = filterVisibleTypes(prioritized.types, lineRange, totalLines);
          const estimatedTokens = Math.ceil(
            visibleTypes.reduce((sum, item) => sum + item.signature.length, 0) / CHARS_PER_TOKEN,
          );

          output.output = formatter.format(originalContent, visibleTypes, {
            totalTypes: visibleTypes.length,
            estimatedTokens,
            isPartialRead: lineRange !== undefined,
            includeDescription: false,
          });
        } catch {
          // Soft-fail: leave the original read output unchanged.
        }

        return;
      }

      if (input.tool !== "write") return;

      const writeContext = currentWrites.get(input.callID);
      currentWrites.delete(input.callID);

      if (!writeContext) return;
      if (!isTypeScriptLikeFile(writeContext.filePath)) return;

      const absoluteFilePath = toAbsolutePath(directory, writeContext.filePath);
      const tsconfigPath = findNearestTsconfig(absoluteFilePath, directory);
      if (!tsconfigPath) return;

      try {
        const lookup = getLookup(absoluteFilePath);
        lookup?.lookup.invalidate(absoluteFilePath);

        const result = getProjectDiagnostics(tsconfigPath, absoluteFilePath);
        if (result.success || result.diagnostics.length === 0) return;

        const formatted = formatDiagnostics(result.diagnostics, path.dirname(tsconfigPath), {
          modifiedFile: absoluteFilePath,
          maxFileErrors: 50,
          maxProjectFiles: 20,
        });

        if (!formatted.trim()) return;
        appendDiagnosticsToOutput(output, formatted);
      } catch {
        // Soft-fail: write success should not depend on diagnostic reporting.
      }
    },
  };
};
