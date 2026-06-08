import { NodeExecutor } from '../types.js';

export const passthroughExecutor: NodeExecutor = (input, _args, signal) => {
  if (signal?.aborted) {
    throw new DOMException("Pipeline execution aborted", "AbortError");
  }
  return input;
};
