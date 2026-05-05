/**
 * Context-Pipe Native OpenCode Plugin
 *
 * NOTE: `tool.execute.after` is declared in the OpenCode plugin Hooks interface
 * but is NOT currently triggered by the OpenCode runtime (as of v1.14.39).
 * See: https://github.com/anomalyco/opencode/issues/25918
 *
 * This plugin is therefore TELEMETRY-ONLY. Output mutation via this hook has
 * no effect. The real interception point is the `pipe_read_file` MCP tool,
 * which is called explicitly by the agent per the AGENTS.md SOP.
 *
 * When OpenCode wires up the trigger in processor.ts, this plugin can be
 * re-enabled for transparent output interception without any agent-side changes.
 */
export const ContextPipePlugin = async (_: any) => {
  return {
    // Hook placeholder — will be activated once OpenCode triggers tool.execute.after
    // "tool.execute.after": async (input: any, output: any) => { ... }
  };
};
};
