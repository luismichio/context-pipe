import { describe, it, expect } from 'vitest';
import { PipelineEngine } from '../src/engine.js';
import { PipeConfig } from '../src/types.js';

describe('PipelineEngine', () => {
  it('should run a pipeline with default nodes (grep and replace)', async () => {
    const engine = new PipelineEngine();
    const config: PipeConfig = {
      name: 'test-pipe',
      description: 'Filter errors and obscure sensitive info',
      nodes: [
        { cmd: 'grep', args: ['-i', 'error'] },
        { cmd: 'replace', args: ['api_key=\\w+', 'api_key=REDACTED'] }
      ]
    };

    const input = [
      'INFO: Startup completed successfully',
      'ERROR: failed to connect, api_key=secret123',
      'WARNING: low disk space',
      'error: failed write operation, api_key=other456'
    ].join('\n');

    const output = await engine.runPipe(config, input);
    
    expect(output).toContain('ERROR: failed to connect, api_key=REDACTED');
    expect(output).toContain('error: failed write operation, api_key=REDACTED');
    expect(output).not.toContain('INFO:');
    expect(output).not.toContain('WARNING:');
    expect(output).not.toContain('secret123');
  });

  it('should support registering custom executors', async () => {
    const engine = new PipelineEngine();
    
    // Register custom uppercase executor
    engine.registerNode('uppercase', (input) => input.toUpperCase());

    const config: PipeConfig = {
      name: 'custom-pipe',
      description: 'Uppercase text',
      nodes: [{ cmd: 'uppercase', args: [] }]
    };

    const output = await engine.runPipe(config, 'hello world');
    expect(output).toBe('HELLO WORLD');
  });

  it('should respect failFast configuration', async () => {
    const engine = new PipelineEngine({ failFast: true });
    const config: PipeConfig = {
      name: 'broken-pipe',
      description: 'Uses an unregistered node',
      nodes: [{ cmd: 'invalid-cmd', args: [] }]
    };

    await expect(engine.runPipe(config, 'test')).rejects.toThrow(
      "Node command 'invalid-cmd' not registered."
    );
  });

  it('should respect AbortSignal and abort execution midway', async () => {
    const engine = new PipelineEngine();
    const controller = new AbortController();

    // Register a custom delayed executor
    engine.registerNode('delay', async (input, _args, signal) => {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => resolve(input), 100);
        signal?.addEventListener('abort', () => {
          clearTimeout(timeout);
          reject(new DOMException("Aborted", "AbortError"));
        });
      });
    });

    const config: PipeConfig = {
      name: 'delayed-pipe',
      description: 'Delayed execution',
      nodes: [{ cmd: 'delay', args: [] }]
    };

    const runPromise = engine.runPipe(config, 'hello', controller.signal);
    
    // Abort immediately
    controller.abort();

    await expect(runPromise).rejects.toThrow();
  });
});
