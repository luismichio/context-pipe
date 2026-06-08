export interface PipeNode {
  cmd: string;
  args: string[];
}

export interface PipeConfig {
  name: string;
  description: string;
  nodes: PipeNode[];
}

export interface PipesJson {
  pipes: PipeConfig[];
}

export type NodeExecutor = (
  input: string,
  args: string[],
  signal?: AbortSignal
) => Promise<string> | string;

export interface EngineOptions {
  failFast?: boolean;
}
