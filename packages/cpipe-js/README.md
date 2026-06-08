# @context-pipe/client

[![npm version](https://img.shields.io/npm/v/@context-pipe/client.svg)](https://www.npmjs.com/package/@context-pipe/client)
[![license](https://img.shields.io/npm/l/@context-pipe/client.svg)](https://github.com/luismichio/context-pipe/blob/main/LICENSE.md)
[![tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](#)
[![protocol parity](https://img.shields.io/badge/protocol%20parity-v0.5.11-blue.svg)](https://github.com/luismichio/context-pipe)

Client-side TypeScript port of the **Context-Pipe (`cpipe`)** pipeline engine. It is designed to run in sandboxed environments (such as web browsers, PWAs, Chrome extensions, and mobile web views) where native OS subprocesses and standard stdio transports are unavailable.

---

## Features

- **Unix Piping Simulation**: Stream-like text transformations sequentially piped through a series of nodes:
  $$\text{Input String} \longrightarrow \text{Node}_1 \longrightarrow \text{Node}_2 \longrightarrow \dots \longrightarrow \text{Output String}$$
- **Schema Parity**: Evaluates the exact same `pipe.json` configuration schema used by the Rust sidecar implementation.
- **Dynamic Extensibility**: Easily register custom platform-dependent nodes (e.g. IndexedDB RAG, CORS fetch proxy) via the Registry Pattern.
- **Cancellation Support**: Full integration with browser `AbortSignal` to cancel long-running executions midway.
- **Resilience Controls**: Configurable `failFast` behavior to either fail early or print warning diagnostics and fallback to passthrough.

---

## Installation

```bash
npm install @context-pipe/client
```

---

## Quick Start

### 1. Basic Usage (Built-in Nodes)

The package comes with standard browser-safe utility nodes (`grep`, `replace` / `sed`, `passthrough`).

```typescript
import { PipelineEngine, PipeConfig } from '@context-pipe/client';

const engine = new PipelineEngine();

const pipe: PipeConfig = {
  name: 'log-filter',
  description: 'Keep error logs and redact API keys',
  nodes: [
    { cmd: 'grep', args: ['-i', 'error'] },
    { cmd: 'replace', args: ['api_key=\\w+', 'api_key=REDACTED'] }
  ]
};

const rawLogs = `
INFO: System startup completed
ERROR: DB connection failed, api_key=secret123
WARNING: High memory usage
error: disk write failed, api_key=another456
`;

const cleanLogs = await engine.runPipe(pipe, rawLogs);
console.log(cleanLogs);
// Output:
// ERROR: DB connection failed, api_key=REDACTED
// error: disk write failed, api_key=REDACTED
```

### 2. Registering Custom Nodes (RAG / Web Fetch)

Extend the engine by registering custom functions to execute actions that require access to browser-sandboxed databases or network relays.

```typescript
const engine = new PipelineEngine({ failFast: true });

// Register a browser-specific IndexedDB RAG lookup node
engine.registerNode('query-rag', async (input, args, signal) => {
  const limit = parseInt(args[0]) || 5;
  const db = await openLocalDatabase();
  return await db.vectorSearch(input, limit, { signal });
});

// Run a pipe configured to trigger RAG augmentation
const output = await engine.runPipe({
  name: 'rag-pipe',
  description: 'Retrieve local context',
  nodes: [{ cmd: 'query-rag', args: ['3'] }]
}, 'How do I configure telemetry?');
```

---

## API Reference

### `PipelineEngine`

The central coordinator class for managing registered executors and running pipeline configurations.

```typescript
class PipelineEngine {
  constructor(options?: EngineOptions);
  
  /**
   * Registers a custom node command executor.
   */
  registerNode(cmd: string, executor: NodeExecutor): void;

  /**
   * Evaluates a pipeline config sequentially on the input text.
   */
  runPipe(pipe: PipeConfig, inputText: string, signal?: AbortSignal): Promise<string>;
}
```

### `NodeExecutor`

The signature required for implementing custom pipeline nodes.

```typescript
type NodeExecutor = (
  input: string,
  args: string[],
  signal?: AbortSignal
) => Promise<string> | string;
```

### `EngineOptions`

Configuration properties for the execution engine.

* **`failFast`** (`boolean`): If `true`, any execution error or missing node registration causes the engine to throw immediately. If `false` (default), the engine logs a warning, skips the failed node, and passes the text through.

---

## Versioning & Compatibility

This package follows **Semantic Versioning (SemVer)** and links its major/minor releases to match the **Context-Pipe Protocol (CPP)** specifications:
- **Baseline Parity**: The initial release starts at `v0.5.11` to match full feature parity with the core Python/Rust implementations up to this specification version.
- **Independent Cycles**: Bug fixes and client-specific enhancements will increment the package version independently. Major/minor changes will align with upgrades to the shared `pipe.json` schema specifications.

---

## License

Apache-2.0
