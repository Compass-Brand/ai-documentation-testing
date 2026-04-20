import type { PluginInput } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";

type OpencodeClient = PluginInput["client"];
type SourceSessionLookup = (sessionID: string) => string | undefined;

function formatTranscript(
  messages: Array<{ info: { role?: string }; parts: Array<Record<string, unknown>> }>,
  limit?: number,
): string {
  const lines: string[] = [];

  for (const message of messages) {
    if (message.info.role === "user") {
      lines.push("## User");
      for (const part of message.parts) {
        if (part.type === "text" && !part.ignored && typeof part.text === "string") {
          lines.push(part.text);
        }
        if (part.type === "file") {
          lines.push(`[Attached: ${typeof part.filename === "string" ? part.filename : "file"}]`);
        }
      }
      lines.push("");
    }

    if (message.info.role === "assistant") {
      lines.push("## Assistant");
      for (const part of message.parts) {
        if (part.type === "text" && typeof part.text === "string") {
          lines.push(part.text);
        }
        if (
          part.type === "tool" &&
          typeof part.tool === "string" &&
          typeof part.state === "object" &&
          part.state !== null &&
          (part.state as { status?: string }).status === "completed"
        ) {
          const title = (part.state as { title?: string }).title ?? "";
          lines.push(`[Tool: ${part.tool}] ${title}`.trim());
        }
      }
      lines.push("");
    }
  }

  const output = lines.join("\n").trim();
  if (messages.length >= (limit ?? 100)) {
    return `${output}\n\n(Showing ${messages.length} most recent messages. Use a higher 'limit' to see more.)`;
  }

  return `${output}\n\n(End of session - ${messages.length} messages)`;
}

export const HandoffSession = (client: OpencodeClient) =>
  tool({
    description: "Create a new session with the handoff prompt as an editable draft",
    args: {
      prompt: tool.schema.string().describe("The generated handoff prompt"),
      files: tool.schema
        .array(tool.schema.string())
        .optional()
        .describe("Repo-local file paths to preload into the new session"),
    },
    async execute(args, context) {
      const sourceReference = `Continuing work from session ${context.sessionID}. When you need more detail you can use read_handoff_session to retrieve the source transcript.`;
      const fileRefs = args.files?.length
        ? args.files.map((filePath) => `@${filePath.replace(/^@/, "")}`).join(" ")
        : "";
      const fullPrompt = fileRefs
        ? `${sourceReference}\n\n${fileRefs}\n\n${args.prompt}`
        : `${sourceReference}\n\n${args.prompt}`;

      await client.tui.executeCommand({ body: { command: "session_new" } });
      await new Promise((resolve) => setTimeout(resolve, 150));
      await client.tui.appendPrompt({ body: { text: fullPrompt } });
      await client.tui.showToast({
        body: {
          title: "Handoff Ready",
          message: "Review and edit the draft, then send",
          variant: "success",
          duration: 4000,
        },
      });

      return "Handoff prompt created in a new session. Review and edit before sending.";
    },
  });

export const ReadHandoffSession = (
  client: OpencodeClient,
  getSourceSessionID: SourceSessionLookup,
) =>
  tool({
    description:
      "Read the conversation transcript from the source session that created this handoff.",
    args: {
      limit: tool.schema
        .number()
        .optional()
        .describe("Maximum number of messages to read (defaults to 100, max 500)"),
    },
    async execute(args, context) {
      const sourceSessionID = getSourceSessionID(context.sessionID);
      if (!sourceSessionID) {
        return "No source handoff session is associated with this session yet.";
      }

      const limit = Math.min(args.limit ?? 100, 500);

      try {
        const response = await client.session.messages({
          path: { id: sourceSessionID },
          query: { limit },
        });

        if (!response.data || response.data.length === 0) {
          return "Source session has no messages or does not exist.";
        }

        return formatTranscript(
          response.data as Array<{ info: { role?: string }; parts: Array<Record<string, unknown>> }>,
          limit,
        );
      } catch (error) {
        return `Could not read source session ${sourceSessionID}: ${error instanceof Error ? error.message : "Unknown error"}`;
      }
    },
  });
