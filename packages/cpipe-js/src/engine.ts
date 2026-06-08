import { PipeConfig, NodeExecutor, EngineOptions } from './types.js';
import { grepExecutor } from './nodes/grep.js';
import { replaceExecutor } from './nodes/replace.js';
import { passthroughExecutor } from './nodes/passthrough.js';

export class PipelineEngine {
  private nodeRegistry: Map<string, NodeExecutor> = new Map();
  private failFast: boolean;

  constructor(options?: EngineOptions) {
    this.failFast = options?.failFast ?? false;
    this.registerDefaultNodes();
  }

  private registerDefaultNodes(): void {
    this.registerNode('grep', grepExecutor);
    this.registerNode('sed', replaceExecutor);
    this.registerNode('replace', replaceExecutor);
    this.registerNode('passthrough', passthroughExecutor);
  }

  // Register a custom command executor dynamically
  registerNode(cmd: string, executor: NodeExecutor): void {
    this.nodeRegistry.set(cmd.toLowerCase(), executor);
  }

  // Execute a named pipe on the input text
  async runPipe(pipe: PipeConfig, inputText: string, signal?: AbortSignal): Promise<string> {
    let currentText = inputText;
    for (const node of pipe.nodes) {
      if (signal?.aborted) {
        throw new DOMException("Pipeline execution aborted", "AbortError");
      }
      
      const executor = this.nodeRegistry.get(node.cmd.toLowerCase());
      if (!executor) {
        if (this.failFast) {
          throw new Error(`Node command '${node.cmd}' not registered.`);
        }
        console.warn(`Node command '${node.cmd}' not registered. Passing text raw.`);
        continue;
      }

      try {
        currentText = await executor(currentText, node.args, signal);
      } catch (err) {
        const isAbort = signal?.aborted || 
                        (err instanceof Error && err.name === 'AbortError') || 
                        (err && typeof err === 'object' && 'name' in err && err.name === 'AbortError');
        if (this.failFast || isAbort) {
          throw err;
        }
        console.error(`Error executing node '${node.cmd}':`, err);
      }
    }
    return currentText;
  }
}
