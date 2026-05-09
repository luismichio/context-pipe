# Context-Pipe: High-Impact Use Cases

To truly understand the power of the **Context-Pipe Platform (CPP)**, you have to stop thinking of it as a tool, and start thinking of it as a **Mental Supply Chain** for your AI agents. 

Below are real-world, high-impact scenarios demonstrating how you can chain Bash commands, Mandate Nodes, and Semantic-Sift to drastically improve your AI's performance, security, and cost.

---

## 1. The Autonomous PR Reviewer
*Scenario: Your agent is reviewing a massive Pull Request containing thousands of lines of React code changes.*

Without CPP, the LLM reads raw, unformatted code, wasting reasoning tokens trying to spot missing semicolons or basic syntax errors.

**The Pipe (`react-pr-reviewer`)**:
1.  **Bash Node (`eslint`)**: Pipes the raw PR diff through your local ESLint to instantly fix basic formatting and syntax issues.
2.  **Mandate Node (`senior-react-engineer`)**: Injects specialized instructions enforcing your company's React 19 architecture rules.
3.  **Refinery Node (`semantic-sift-cli`)**: Semantically condenses the diff, highlighting only the functional changes.

```json
{
  "name": "react-pr-reviewer",
  "nodes": [
    { "cmd": "npx", "args": ["eslint", "--stdin", "--fix-dry-run"], "shell": true },
    { "type": "script", "cmd": "senior-react-engineer" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.7"] }
  ]
}
```
**The Result:** The LLM receives pre-formatted code wrapped in senior-level architectural instructions, allowing it to focus entirely on deep logic flaws rather than syntax.

---

## 2. The Kubernetes Incident Responder
*Scenario: A pod crashes in production, and your agent runs `kubectl logs` which dumps 50,000 lines of output.*

Without CPP, the context window floods instantly, the LLM hallucinates, or the request fails due to token limits.

**The Pipe (`k8s-incident-responder`)**:
1.  **Bash Node (`grep`)**: Instantly filters the 50,000 lines down to only those containing "Error", "Exception", or "Panic".
2.  **Mandate Node (`pii-masker`)**: Scrubs the remaining logs for email addresses, IPs, or auth tokens to ensure customer data never leaves your machine.
3.  **Refinery Node (`semantic-sift-cli logs`)**: Uses the blazingly fast heuristic sieve to strip away repetitive timestamps and Kubernetes container IDs.

```json
{
  "name": "k8s-incident-responder",
  "nodes": [
    { "cmd": "grep", "args": ["-iE", "error|exception|panic"], "shell": true },
    { "type": "script", "cmd": "pii-masker" },
    { "cmd": "semantic-sift-cli", "args": ["logs"] }
  ]
}
```
**The Result:** 50,000 lines of noise are reduced to 50 lines of pure, secure, actionable signal.

---

## 3. The Research Synthesizer (Web to Knowledge)
*Scenario: Your agent fetches a competitor's 100-page API documentation website to learn how to integrate it.*

Without CPP, the agent downloads raw HTML, flooding its context with CSS, JavaScript, and navigation menus. With a Shadow MCP server like Firecrawl registered in `pipes.json` but hidden from the IDE tool list, the agent never sees the bloat — it sees only the distilled knowledge.

**The Pipe (`web-researcher`)**:
1.  **MCP Node (`firecrawl/scrape`) *(Phase 7.5)***: Fetches the live page as clean text via the Firecrawl MCP server — no curl, no raw HTML. The server is registered in `pipes.json` `servers` block but not exposed to the IDE as a standalone tool.
2.  **Node (`markitdown` or `pandoc`)**: Converts the result into structured Markdown.
3.  **Mandate Node (`api-integration-expert`)**: Injects instructions to focus only on API endpoints and authentication methods.
4.  **Refinery Node (`semantic-sift-cli doc`)**: Performs heavy semantic compression (`rate: 0.3`), stripping marketing fluff and retaining only core technical concepts.

```json
{
  "name": "web-researcher",
  "nodes": [
    {
      "type": "mcp",
      "server": "firecrawl",
      "tool": "scrape",
      "input_key": "url",
      "help_msg": "Firecrawl MCP server not reachable. Check FIRECRAWL_API_KEY."
    },
    { "cmd": "markitdown" },
    { "type": "script", "cmd": "api-integration-expert" },
    { "cmd": "semantic-sift-cli", "args": ["doc", "--rate", "0.3"] }
  ]
}
```

> **Note:** The `firecrawl` server entry lives in the `servers` block of `pipes.json` (or `~/.mcp-pipe.json`) and is never registered in your IDE — keeping it shadow. Until Phase 7.5 ships, replace the MCP node with `{ "cmd": "markitdown" }` and pipe a pre-fetched HTML file through stdin.

**The Result:** The LLM reads a highly concentrated, technically dense summary of the API, costing pennies instead of dollars in API tokens — with the web scraper remaining invisible to the agent's tool list.

---

## 4. The Extreme Codebase Auditor
*Scenario: You ask your agent to "Find all authentication vulnerabilities in the backend directory." The agent uses `grep_search` and returns 20 massive files.*

Without CPP, the agent gets overwhelmed by the sheer volume of code and misses subtle injection flaws.

**The Pipe (`security-auditor`)**:
1.  **Bash Node (`trufflehog` or `bandit`)**: Runs a fast, local SAST (Static Application Security Testing) tool over the code stream to flag known vulnerability patterns.
2.  **Mandate Node (`owasp-top-10`)**: Injects strict OWASP security guidelines for the LLM to evaluate the flagged code against.
3.  **Refinery Node (`semantic-sift-cli semantic`)**: Compresses the code, retaining only the logic flow around the flagged areas.

```json
{
  "name": "security-auditor",
  "nodes": [
    { "cmd": "bandit", "args": ["-f", "json", "-s", "B101,B102", "-"], "shell": true },
    { "type": "script", "cmd": "owasp-security-expert" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.6"] }
  ]
}
```
**The Result:** Your LLM transforms from a generic coding assistant into a highly specialized security auditor, guided by deterministic local tools.

---

## 5. The Multi-Stage Refinery (Double Sifting)
*Scenario: Analyzing a massive, mixed-format CI/CD failure log that contains both raw machine hex codes and verbose developer tracebacks.*

Sometimes data is so noisy you need both a machete and a scalpel. You can chain different modes of Sift within the exact same pipe.

**The Pipe (`ci-cd-autopsy`)**:
1.  **Refinery Node (`semantic-sift-cli logs`)**: First, use the ultra-fast heuristic sieve (the machete) to instantly strip out thousands of timestamps, IP addresses, and progress bars.
2.  **Mandate Node (`build-engineer`)**: Inject instructions to focus strictly on dependency conflicts and linking errors.
3.  **Refinery Node (`semantic-sift-cli semantic`)**: Finally, use the neural engine (the scalpel) to semantically compress the remaining verbose developer tracebacks.

```json
{
  "name": "ci-cd-autopsy",
  "nodes": [
    { "cmd": "semantic-sift-cli", "args": ["logs"] },
    { "type": "script", "cmd": "build-engineer" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.4"] }
  ]
}
```
**The Result:** A 10MB mixed-format build log is structurally sanitized, then semantically pruned, returning only the core reasoning behind the build failure.

---

## 6. The Visual QA Bot (Playwright SPA Crawler)
*Scenario: Your agent needs to review a complex Single Page Application (SPA) for Accessibility (a11y) violations, but the raw HTML is generated dynamically by React/Vue/Svelte.*

A standard `curl` fails here because the DOM hasn't rendered. You need a headless browser.

**The Pipe (`spa-a11y-reviewer`)**:
1.  **Bash Node (`node dump_dom.js`)**: A tiny local script uses Playwright to launch a headless browser, wait for JS hydration, and dump the fully rendered HTML Accessibility Tree to `stdout`.
2.  **Node (`markitdown`)**: Converts the massive rendered HTML DOM into clean, structured Markdown.
3.  **Mandate Node (`a11y-auditor`)**: Injects strict WCAG (Web Content Accessibility Guidelines) instructions.
4.  **Refinery Node (`semantic-sift-cli semantic`)**: Compresses the DOM, focusing the LLM's attention purely on missing ARIA labels and structural flaws.

```json
{
  "name": "spa-a11y-reviewer",
  "nodes": [
    { "cmd": "node", "args": ["scripts/dump_dom.js"], "shell": true },
    { "cmd": "python", "args": ["-m", "markitdown"] },
    { "type": "script", "cmd": "a11y-auditor" },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.5"] }
  ]
}
```
**The Result:** The LLM effortlessly audits highly dynamic web applications without choking on megabytes of React hydration boilerplate.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
