import { NodeExecutor } from '../types.js';

export const replaceExecutor: NodeExecutor = (input, args, signal) => {
  if (signal?.aborted) {
    throw new DOMException("Pipeline execution aborted", "AbortError");
  }

  // Expects arguments: [searchPattern, replacement]
  if (args.length < 2) {
    return input; // Insufficient arguments, return original
  }

  const searchPattern = args[0];
  const replacement = args[1];

  // Perform a global regex replace
  const regex = new RegExp(searchPattern, 'g');
  
  if (signal?.aborted) {
    throw new DOMException("Pipeline execution aborted", "AbortError");
  }
  
  const result = input.replace(regex, replacement);
  
  if (signal?.aborted) {
    throw new DOMException("Pipeline execution aborted", "AbortError");
  }

  return result;
};
