import * as fs from "node:fs/promises";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { Config } from "@opencode-ai/sdk";

const COMPASS_BEADS_CLI_USAGE = `## Compass Beads CLI Usage

Use the shell tool to run \`bd\` directly. Do not invent a parallel task tracker.

Primary commands for this wrapper:

- \`bd prime\` - recover beads workflow context
- \`bd ready\` - show ready work
- \`bd show <id>\` - show issue details
- \`bd list --status open\` - list issues
- \`bd blocked\` - show blocked work
- \`bd stats\` - show project statistics
- \`bd create --title "..." --type task --priority 2\` - create issue
- \`bd update <id> --status in_progress\` - update status
- \`bd close <id> --reason "..."\` - close issue
- \`bd sync\` - sync beads state with git

If \`bd\` is missing or the repo is not initialized, stop and report that clearly.`;

const COMPASS_BEADS_POLICY = `## Compass Policy

- \`bd\` is the issue and task system of record.
- Do not create parallel markdown TODO lists as the authoritative tracker.
- Keep BMAD artifacts in their documented lanes.
- When ending a work session, follow the repo's required sync/commit/push protocol.`;

const COMPASS_BEADS_SUBAGENT_CONTEXT = `## Subagent Context

You are the Compass beads task agent. Your final message should be concise and useful to the calling agent.

For status requests:

- run the necessary \`bd\` commands
- summarize the result in plain language
- do not dump raw command output when a short summary will do

For task work:

- inspect the issue
- claim or set it in progress before working
- complete the requested change
- file newly discovered follow-up work in \`bd\`
- close the issue only when the work is actually done

Always keep \`bd\` authoritative and avoid creating parallel task tracking.`;

export const COMPASS_BEADS_TASK_AGENT = "compass-beads-task-agent";

export const BEADS_GUIDANCE = `<compass-beads-guidance>
${COMPASS_BEADS_CLI_USAGE}

${COMPASS_BEADS_POLICY}
</compass-beads-guidance>`;

function getVendorDir(): string {
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  return path.join(__dirname, "vendor");
}

interface ParsedMarkdown {
  frontmatter: Record<string, string | undefined>;
  body: string;
}

function parseMarkdownWithFrontmatter(content: string): ParsedMarkdown | null {
  const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/;
  const match = content.match(frontmatterRegex);
  if (!match) return null;

  const frontmatterStr = match[1];
  const body = match[2];
  if (frontmatterStr === undefined || body === undefined) return null;

  const frontmatter: Record<string, string | undefined> = {};
  for (const line of frontmatterStr.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const colonIndex = trimmed.indexOf(":");
    if (colonIndex === -1) continue;

    const key = trimmed.slice(0, colonIndex).trim();
    let value = trimmed.slice(colonIndex + 1).trim();
    if (
      (value.startsWith("\"") && value.endsWith("\""))
      || (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    frontmatter[key] = value;
  }

  return { frontmatter, body: body.trim() };
}

async function readVendorFile(relativePath: string): Promise<string | null> {
  try {
    return await fs.readFile(path.join(getVendorDir(), relativePath), "utf-8");
  } catch {
    return null;
  }
}

async function listVendorFiles(relativePath: string): Promise<string[]> {
  try {
    return await fs.readdir(path.join(getVendorDir(), relativePath));
  } catch {
    return [];
  }
}

export async function loadAgent(): Promise<Config["agent"]> {
  const content = await readVendorFile("agents/task-agent.md");
  if (!content) return {};

  const parsed = parseMarkdownWithFrontmatter(content);
  if (!parsed) return {};

  const description =
    parsed.frontmatter.description ?? "Compass beads task completion agent";

  return {
    [COMPASS_BEADS_TASK_AGENT]: {
      description,
      prompt: `${COMPASS_BEADS_CLI_USAGE}\n\n${COMPASS_BEADS_POLICY}\n\n${COMPASS_BEADS_SUBAGENT_CONTEXT}\n\n${parsed.body}`,
      mode: "subagent",
    },
  };
}

export async function loadCommands(): Promise<Config["command"]> {
  const files = await listVendorFiles("commands");
  const commands: Config["command"] = {};

  for (const file of files) {
    if (!file.endsWith(".md")) continue;

    const content = await readVendorFile(`commands/${file}`);
    if (!content) continue;

    const parsed = parseMarkdownWithFrontmatter(content);
    if (!parsed) continue;

    const baseName = file.replace(".md", "");
    const name = `bd-${baseName}`;
    const argHint = parsed.frontmatter["argument-hint"];
    const baseDescription = parsed.frontmatter.description ?? name;
    const description = argHint
      ? `${baseDescription} (${argHint})`
      : baseDescription;

    commands[name] = {
      description,
      template: `${COMPASS_BEADS_CLI_USAGE}\n\n${COMPASS_BEADS_POLICY}\n\n${parsed.body}`,
    };
  }

  return commands;
}
