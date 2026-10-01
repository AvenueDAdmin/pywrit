# writ-mcp

The [Writ](https://withwrit.com) gate as an MCP server. Give any MCP-compatible
agent commit-time control: the agent calls Writ **before** a consequential
write, gets back `ALLOW`, `DENY`, or `STEP_UP`, and every outcome creates an
audit receipt.

<!-- mcp-name: io.github.withwrit/writ -->

## Install

```bash
pip install writ-mcp
```

Requires Python 3.9+. Installs the `writ-mcp` command (stdio transport).

## Configure

```bash
export WRIT_API_KEY="writ_..."        # required; get one free: POST /v1/keys with an email
export WRIT_SPONSOR_TOKEN="..."       # only for sponsor tools (grant, revoke, reinstate)
# export WRIT_BASE_URL="..."          # default: https://api.withwrit.com
```

## Add to your agent

Claude Code:

```bash
claude mcp add writ --env WRIT_API_KEY="$WRIT_API_KEY" -- writ-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "writ": {
      "command": "writ-mcp",
      "env": { "WRIT_API_KEY": "writ_..." }
    }
  }
}
```

Any MCP client (generic stdio config):

```json
{
  "command": "writ-mcp",
  "env": {
    "WRIT_API_KEY": "writ_...",
    "WRIT_SPONSOR_TOKEN": "writ_sp_..."
  }
}
```

Hermes (NousResearch/hermes-agent) catalog entry — once published, this
package is installable from the `optional-mcps` catalog:

```bash
hermes mcp install writ
```

## The check-before-write loop

The tool descriptions teach the agent this flow, but the short version:

1. `writ_check(sponsor_id, agent_id, verb, target, purpose)` — before the write.
2. `ALLOW` → you get a 90-second `authToken` bound to that exact write.
3. `writ_verify_token(auth_token, verb, target, purpose)` — immediately before
   executing, to prove the authorization still matches what you're doing.
4. `DENY` → do not proceed. `STEP_UP` → a human sponsor approves
   (via `writ_grant` or the dashboard), then check again.

## Tools

| Tool | Who | What |
|---|---|---|
| `writ_check` | agent | Decision + 90s purpose-bound token |
| `writ_verify_token` | agent | Commit-time token verification |
| `writ_grant` | sponsor | Approve a STEP_UP (one-time grant) |
| `writ_revoke` / `writ_reinstate` | sponsor | Kill switch on/off for a principal |
| `writ_receipts` | agent | Audit trail of decisions |
| `writ_policy` | agent | Tenant verb policy |
| `writ_sandbox` | anyone | Free 90-second demo grant, no key needed |

Try it with no key: `writ_sandbox` → `writ_check` with `verb="demo_write"`.

## Source

Public repo: [withwrit/pywrit](https://github.com/withwrit/pywrit) (`mcp/`
directory). License: MIT.
