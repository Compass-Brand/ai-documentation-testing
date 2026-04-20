import type { Plugin } from "@opencode-ai/plugin";
import {
  buildSyntheticFileParts,
  parseFileReferences,
  parseSourceSessionReference,
} from "./files";
import { HandoffSession, ReadHandoffSession } from "./tools";

const HANDOFF_COMMAND = `GOAL: You are creating a Compass handoff message to continue work in a new session.

<context>
Compass sessions should preserve execution context, not restart discovery from scratch.

A good handoff lets the next session continue implementation immediately while keeping Compass control surfaces authoritative:

- bd issue ids and statuses
- BMAD artifact paths
- relevant source and test files
- current branch or worktree context when it matters
- what was verified, what was not verified, and why
</context>

<instructions>
Analyze this conversation and produce a focused handoff for the next session.

1. Identify the repo-local files that should be loaded into the next session.

   Include files that are likely to be edited next, tests, configs, and key reference docs.
   Target 8-15 files for normal work, up to 20 for complex work.
   Only include repo-local files that are actually helpful for continuation.

2. Draft the continuation context.

   Preserve:
   - the active objective
   - the next concrete step
   - active bd issue ids or task refs when known
   - relevant planning and docs artifact paths
   - decisions, constraints, and user preferences
   - blockers, caveats, and residual risks
   - tests run, tests not run, and why

   Exclude:
   - back-and-forth conversation
   - dead ends unless they remain important constraints
   - prose that would replace bd or BMAD as the source of truth

3. Keep the handoff concise but implementation-ready.

<user_input>
This is what the next session should focus on. Shape the handoff toward this goal without doing new investigation.

USER: $ARGUMENTS
</user_input>

---

After generating the handoff message, IMMEDIATELY call handoff_session with your prompt and files:
\`handoff_session(prompt="...", files=["src/foo.ts", "src/bar.ts", ...])\``;

export const CompassHandoffPlugin: Plugin = async (ctx) => {
  const processedSessions = new Set<string>();
  const sourceSessionBySessionID = new Map<string, string>();

  return {
    config: async (config) => {
      config.command = config.command || {};
      config.command.handoff = {
        description: "Create a Compass-aware handoff prompt for a new session",
        template: HANDOFF_COMMAND,
      };
    },

    tool: {
      handoff_session: HandoffSession(ctx.client),
      read_handoff_session: ReadHandoffSession(
        ctx.client,
        (sessionID) => sourceSessionBySessionID.get(sessionID),
      ),
    },

    "chat.message": async (_input, output) => {
      const sessionID = output.message.sessionID;
      if (processedSessions.has(sessionID)) return;

      const text = output.parts
        .filter(
          (part): part is typeof part & { type: "text"; text: string } =>
            part.type === "text" && !part.synthetic && typeof part.text === "string",
        )
        .map((part) => part.text)
        .join("\n");

      const sourceSessionID = parseSourceSessionReference(text);
      if (!sourceSessionID) return;

      processedSessions.add(sessionID);
      sourceSessionBySessionID.set(sessionID, sourceSessionID);

      const fileRefs = parseFileReferences(text);
      if (fileRefs.size === 0) return;

      const fileParts = await buildSyntheticFileParts(ctx.directory, fileRefs);
      if (fileParts.length === 0) return;

      await ctx.client.session.prompt({
        path: { id: sessionID },
        body: {
          noReply: true,
          model: output.message.model,
          agent: output.message.agent,
          parts: fileParts,
        },
      });
    },

    event: async ({ event }) => {
      if (event.type !== "session.deleted") return;

      const sessionID = event.properties.info.id;
      processedSessions.delete(sessionID);
      sourceSessionBySessionID.delete(sessionID);
    },
  };
};
