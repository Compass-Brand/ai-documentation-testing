import * as fs from "node:fs/promises";
import * as path from "node:path";
import type { TextPartInput } from "@opencode-ai/sdk";
import { formatFileContent, isBinaryFile } from "./vendor";

export const FILE_REGEX = /(?<![\w`])@(\.?[^\s`,.]*(?:\.[^\s`,.]+)*)/g;
export const SOURCE_SESSION_REGEX = /Continuing work from session ([^\s.]+)/;

export function parseFileReferences(text: string): Set<string> {
  const refs = new Set<string>();

  for (const match of text.matchAll(FILE_REGEX)) {
    if (match[1]) refs.add(match[1]);
  }

  return refs;
}

export function parseSourceSessionReference(text: string): string | null {
  const match = text.match(SOURCE_SESSION_REGEX);
  return match?.[1] ?? null;
}

function isWithinDirectory(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

export async function buildSyntheticFileParts(
  directory: string,
  refs: Set<string>,
): Promise<TextPartInput[]> {
  const parts: TextPartInput[] = [];

  for (const ref of refs) {
    const filepath = path.resolve(directory, ref);
    if (!isWithinDirectory(directory, filepath)) continue;

    try {
      const stats = await fs.stat(filepath);
      if (!stats.isFile()) continue;
      if (await isBinaryFile(filepath)) continue;

      const content = await fs.readFile(filepath, "utf-8");

      parts.push({
        type: "text",
        synthetic: true,
        text: `Called the Read tool with the following input: ${JSON.stringify({ filePath: filepath })}`,
      });
      parts.push({
        type: "text",
        synthetic: true,
        text: formatFileContent(filepath, content),
      });
    } catch {
      // Soft-fail: skip unreadable or missing files.
    }
  }

  return parts;
}
