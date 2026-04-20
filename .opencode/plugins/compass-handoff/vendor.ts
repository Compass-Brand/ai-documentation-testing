import * as fs from "node:fs/promises";
import * as path from "node:path";

export const DEFAULT_READ_LIMIT = 2000;
export const MAX_LINE_LENGTH = 2000;

const BINARY_EXTENSIONS = new Set([
  ".zip",
  ".tar",
  ".gz",
  ".exe",
  ".dll",
  ".so",
  ".class",
  ".jar",
  ".war",
  ".7z",
  ".doc",
  ".docx",
  ".xls",
  ".xlsx",
  ".ppt",
  ".pptx",
  ".odt",
  ".ods",
  ".odp",
  ".bin",
  ".dat",
  ".obj",
  ".o",
  ".a",
  ".lib",
  ".wasm",
  ".pyc",
  ".pyo",
]);

export async function isBinaryFile(filepath: string): Promise<boolean> {
  const ext = path.extname(filepath).toLowerCase();
  if (BINARY_EXTENSIONS.has(ext)) return true;

  try {
    const buffer = await fs.readFile(filepath);
    if (!buffer || buffer.length === 0) return false;

    const bytes = buffer.subarray(0, Math.min(4096, buffer.length));
    let nonPrintableCount = 0;

    for (let index = 0; index < bytes.length; index++) {
      const byte = bytes[index];
      if (byte === undefined) continue;
      if (byte === 0) return true;
      if (byte < 9 || (byte > 13 && byte < 32)) {
        nonPrintableCount += 1;
      }
    }

    return nonPrintableCount / bytes.length > 0.3;
  } catch {
    return false;
  }
}

export function formatFileContent(_filepath: string, content: string): string {
  const lines = content.split("\n");
  const raw = lines.slice(0, DEFAULT_READ_LIMIT).map((line) =>
    line.length > MAX_LINE_LENGTH ? `${line.substring(0, MAX_LINE_LENGTH)}...` : line,
  );
  const formatted = raw.map(
    (line, index) => `${(index + 1).toString().padStart(5, "0")}| ${line}`,
  );

  let output = "<file>\n";
  output += formatted.join("\n");

  if (lines.length > formatted.length) {
    output += `\n\n(File has more lines. Use 'offset' parameter to read beyond line ${formatted.length})`;
  } else {
    output += `\n\n(End of file - total ${lines.length} lines)`;
  }

  output += "\n</file>";
  return output;
}
