/**
 * Context-Pipe Native OpenCode Plugin
 */
export default function (api: any) {
  api.on("tool.execute.after", async (event: any) => {
    const rawContent = event.result;
    if (typeof rawContent !== 'string' || rawContent.length < 500) return;
    if (rawContent.includes("--- [Context-Pipe: Native Execution] ---")) return;
    try {
      const pythonExe = "C:/Users/luism/Workbench/GitHub/context-pipe/venv/Scripts/python.exe";
      const payload = { hook_event_name: "AfterTool", tool_name: event.toolName, result: rawContent };
      const { execSync } = require('child_process');
      const response = execSync(`"${pythonExe}" -m context_pipe.orchestrator wrap`, { input: JSON.stringify(payload), encoding: 'utf-8' });
      const siftedData = JSON.parse(response);
      if (siftedData?.result) {
         event.result = siftedData.result;
      }
    } catch (error) { console.error("[Context-Pipe Plugin] failed:", error); }
  });
};
