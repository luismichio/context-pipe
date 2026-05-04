# Context-Pipe: High-Impact Use Cases

To truly understand the power of the **Context-Pipe Platform (CPP)**, you have to stop thinking of it as a tool, and start thinking of it as a **Mental Supply Chain** for your AI agents. 

Below are real-world, high-impact scenarios demonstrating how you can chain Bash commands, Skill Nodes, and Semantic-Sift to drastically improve your AI's performance, security, and cost.

---

## 1. The Autonomous PR Reviewer
*Scenario: Your agent is reviewing a massive Pull Request containing thousands of lines of React code changes.*

Without CPP, the LLM reads raw, unformatted code, wasting reasoning tokens trying to spot missing semicolons or basic syntax errors.

**The Pipe (`react-pr-reviewer`)**:
1.  **Bash Node (`eslint`)**: Pipes the raw PR diff through your local ESLint to instantly fix basic formatting and syntax issues.
2.  **Skill Node (`senior-react-engineer`)**: Injects a specialized prompt enforcing your company's specific React 19 architecture rules.
3.  **Refinery Node (`semantic-sift-cli`)**: Semantically condenses the diff, highlighting only the functional changes.

```json
{
  "name": "react-pr-reviewer",
  "nodes": [
    { "cmd": "npx", "args": ["eslint", "--stdin", "--fix-dry-run"], "shell": true },
    { "cmd": "context-pipe-skill", "args": ["senior-react-engineer"] },
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
2.  **Skill Node (`pii-masker`)**: Scrubs the remaining logs for email addresses, IPs, or auth tokens to ensure customer data never leaves your machine.
3.  **Refinery Node (`semantic-sift-cli logs`)**: Uses the blazingly fast heuristic sieve to strip away repetitive timestamps and Kubernetes container IDs.

```json
{
  "name": "k8s-incident-responder",
  "nodes": [
    { "cmd": "grep", "args": ["-iE", "error|exception|panic"], "shell": true },
    { "cmd": "context-pipe-skill", "args": ["pii-masker"] },
    { "cmd": "semantic-sift-cli", "args": ["logs"] }
  ]
}
```
**The Result:** 50,000 lines of noise are reduced to 50 lines of pure, secure, actionable signal.

---

## 3. The Research Synthesizer (Web to Knowledge)
*Scenario: Your agent fetches a competitor's 100-page API documentation website to learn how to integrate it.*

Without CPP, the agent downloads raw HTML, flooding its context with CSS, JavaScript, and navigation menus.

**The Pipe (`web-researcher`)**:
1.  **Bash Node (`curl`)**: Fetches the raw HTML.
2.  **Node (`markitdown` or `pandoc`)**: Converts the messy HTML into clean Markdown.
3.  **Skill Node (`technical-writer`)**: Injects instructions telling the LLM to focus only on API endpoints and authentication methods.
4.  **Refinery Node (`semantic-sift-cli doc`)**: Performs a heavy semantic compression (`rate: 0.3`), stripping away marketing fluff and keeping only the core technical concepts.

```json
{
  "name": "web-researcher",
  "nodes": [
    { "cmd": "python", "args": ["-m", "markitdown"] },
    { "cmd": "context-pipe-skill", "args": ["api-integration-expert"] },
    { "cmd": "semantic-sift-cli", "args": ["doc", "--rate", "0.3"] }
  ]
}
```
**The Result:** The LLM reads a highly concentrated, technically dense summary of the API, costing pennies instead of dollars in API tokens.

---

## 4. The Extreme Codebase Auditor
*Scenario: You ask your agent to "Find all authentication vulnerabilities in the backend directory." The agent uses `grep_search` and returns 20 massive files.*

Without CPP, the agent gets overwhelmed by the sheer volume of code and misses subtle injection flaws.

**The Pipe (`security-auditor`)**:
1.  **Bash Node (`trufflehog` or `bandit`)**: Runs a fast, local SAST (Static Application Security Testing) tool over the code stream to flag known vulnerability patterns.
2.  **Skill Node (`owasp-top-10`)**: Injects strict OWASP security guidelines for the LLM to evaluate the flagged code against.
3.  **Refinery Node (`semantic-sift-cli semantic`)**: Compresses the code, retaining only the logic flow around the flagged areas.

```json
{
  "name": "security-auditor",
  "nodes": [
    { "cmd": "bandit", "args": ["-f", "json", "-s", "B101,B102", "-"], "shell": true },
    { "cmd": "context-pipe-skill", "args": ["owasp-security-expert"] },
    { "cmd": "semantic-sift-cli", "args": ["semantic", "--rate", "0.6"] }
  ]
}
```
**The Result:** Your LLM transforms from a generic coding assistant into a highly specialized security auditor, guided by deterministic local tools.

---
*Building High-Fidelity Infrastructure for the Studio of Two.*
