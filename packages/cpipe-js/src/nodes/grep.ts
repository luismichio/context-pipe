import { NodeExecutor } from '../types.js';

export const grepExecutor: NodeExecutor = (input, args, signal) => {
  if (signal?.aborted) {
    throw new DOMException("Pipeline execution aborted", "AbortError");
  }

  // Parse arguments: e.g. -i for case-insensitive
  const isCaseInsensitive = args.includes('-i');
  // Filter out flags to get standard queries/regex patterns
  const patternArgs = args.filter(arg => !arg.startsWith('-'));
  
  if (patternArgs.length === 0) {
    return input; // No pattern provided, pass through
  }

  const patternStr = patternArgs[0];
  const flags = isCaseInsensitive ? 'i' : '';
  const regex = new RegExp(patternStr, flags);

  const lines = input.split(/\r?\n/);
  const matchedLines = lines.filter(line => {
    if (signal?.aborted) {
      throw new DOMException("Pipeline execution aborted", "AbortError");
    }
    return regex.test(line);
  });

  return matchedLines.join('\n');
};
