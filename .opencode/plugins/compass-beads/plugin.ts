import type { Plugin, PluginInput } from "@opencode-ai/plugin";
import { BEADS_GUIDANCE, COMPASS_BEADS_TASK_AGENT, loadAgent, loadCommands } from "./vendor";

type OpencodeClient = PluginInput["client"];

async function getSessionContext(
  client: OpencodeClient,
  sessionID: string,
): Promise<
  { model?: { providerID: string; modelID: string }; agent?: string } | undefined
> {
  try {
    const response = await client.session.messages({
      path: { id: sessionID },
      query: { limit: 50 },
    });

    if (response.data) {
      for (const msg of response.data) {
        if (msg.info.role === "user" && "model" in msg.info && msg.info.model) {
          return { model: msg.info.model, agent: msg.info.agent };
        }
      }
    }
  } catch {
    // Let OpenCode continue normally if we cannot recover session context.
  }

  return undefined;
}

async function injectBeadsContext(
  client: OpencodeClient,
  $: PluginInput["$"],
  sessionID: string,
  context?: { model?: { providerID: string; modelID: string }; agent?: string },
): Promise<void> {
  try {
    const primeOutput = await $`bd prime`.text();
    if (!primeOutput || primeOutput.trim() === "") return;

    const beadsContext = `<compass-beads-context>
${primeOutput.trim()}
</compass-beads-context>

${BEADS_GUIDANCE}`;

    await client.session.prompt({
      path: { id: sessionID },
      body: {
        noReply: true,
        model: context?.model,
        agent: context?.agent,
        parts: [{ type: "text", text: beadsContext, synthetic: true }],
      },
    });
  } catch {
    // Silent no-op when bd is unavailable or the repo is not initialized.
  }
}

export const CompassBeadsPlugin: Plugin = async ({ client, $ }) => {
  const [commands, agents] = await Promise.all([loadCommands(), loadAgent()]);
  const injectedSessions = new Set<string>();

  async function shouldInject(agentName: string | undefined): Promise<boolean> {
    if (!agentName || agentName === COMPASS_BEADS_TASK_AGENT) return true;

    const response = await client.app.agents().catch(() => undefined);
    const agent = response?.data?.find((item) => item.name === agentName);
    if (agent) {
      return agent.mode === "primary" || agent.mode === "all";
    }

    return true;
  }

  return {
    "chat.message": async (_input, output) => {
      const sessionID = output.message.sessionID;
      if (injectedSessions.has(sessionID)) return;

      if (!(await shouldInject(output.message.agent))) {
        injectedSessions.add(sessionID);
        return;
      }

      try {
        const existing = await client.session.messages({
          path: { id: sessionID },
        });

        if (existing.data) {
          const hasBeadsContext = existing.data.some((msg) => {
            const parts = (msg as { parts?: Array<{ type?: string; text?: string }> }).parts
              ?? (msg.info as { parts?: Array<{ type?: string; text?: string }> }).parts
              ?? [];
            return parts.some(
              (part) =>
                part.type === "text" && part.text?.includes("<compass-beads-context>"),
            );
          });

          if (hasBeadsContext) {
            injectedSessions.add(sessionID);
            return;
          }
        }
      } catch {
        // If we cannot inspect the session history, attempt a normal inject.
      }

      injectedSessions.add(sessionID);
      await injectBeadsContext(client, $, sessionID, {
        model: output.message.model,
        agent: output.message.agent,
      });
    },

    event: async ({ event }) => {
      if (event.type !== "session.compacted") return;

      const sessionID = event.properties.sessionID;
      const context = await getSessionContext(client, sessionID);
      if (!(await shouldInject(context?.agent))) return;

      await injectBeadsContext(client, $, sessionID, context);
    },

    config: async (config) => {
      config.command = { ...config.command, ...commands };
      config.agent = { ...config.agent, ...agents };
    },
  };
};
