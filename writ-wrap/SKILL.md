---
name: writ-wrap
description: Wrap a user's codebase with Writ policy gates when they ask "wrap my site in Writ" or similar.
triggers:
  - wrap my site in writ
  - wrap this repo in writ
  - wrap my code in writ
  - instrument my codebase with writ
  - add writ policy checks to my project
  - gate my writes with writ
---

# writ-wrap

A runbook for AI agents (Hermes, Claude Code, Kimi, etc.) that wraps a user's
codebase with [Writ](https://withwrit.com) policy gates. The goal is to find
every consequential write in the project, map it to a Writ verb, show the user
exactly what will be instrumented, apply the gates, and verify that a live
`ALLOW` decision lands in the audit log.

**Customer-facing language:** say **"audit log"**, not "receipts". The CLI
command is `writ receipts`, but to the user it is the tamper-evident audit log
in the Writ portal.

**Coverage honesty:** `writ scan` is local and deterministic, but it does not
catch every write. The risk report lists gaps every time. Do not claim full
coverage; claim only that every finding was gated and verified.

---

## 1. Install

Ask the user what language the project uses, then install the right package.

**Python projects:**

```bash
pip install pywrit
```

**TypeScript / JavaScript projects (or mixed Python/TS repos):**

```bash
pip install 'pywrit[polyglot]'
```

The polyglot extra adds tree-sitter support so `writ scan` can find write sites
in `.ts` and `.js` files. It does **not** let `--apply` rewrite TS/JS files;
TS/JS findings must be gated by hand.

> Alternative for agents with no shell access: see [MCP server path](#mcp-server-alternative-for-agents-without-shell-access).

---

## 2. Scan the repo and read the risk report

Run the scanner from the project root:

```bash
writ scan .
```

What you will see:

- `files scanned` — how many source files were analyzed.
- `write sites` — functions or methods that perform a consequential write.
- `gated` — how many already call `writ_check(...)` / `_writ_check(...)`.
- `verbs discovered` — inferred verbs such as `payments.refund`, `crm.update`, or
  `db.write`.
- A **risk report** (0–100) and a unified diff of the instrumentation that
  `--apply` would insert.
- A **gaps** section listing patterns the scanner could not classify (e.g.
  dynamically built SQL, third-party SDK calls, deferred queues).

Explain the report to the user in plain language:

> "Writ found N write sites across these files. X are already gated. The risk
> score is Y/100, driven by ungated database/HTTP/file/email/queue writes and
> the gaps listed here. The gaps are places you'll still need to review by hand."

For a score-only summary:

```bash
writ scan . --score
```

For the guided single-verb flow, skip ahead to step 4 and use `writ wrap .`
instead of `writ scan . --apply`.

---

## 3. Map findings to Writ verbs

Every write site must map to a verb before it can be gated. The scanner infers
verbs from file path and function name and writes them to `writ-policy.json`.

**Before applying instrumentation, check that every verb exists in the
current policy.** The gate will reject unknown verbs.

Read the local policy file and the remote policy:

```bash
# Local inferred policy (created by the scan)
cat writ-policy.json

# Remote tenant policy, once you have a key
writ policy --key "$WRIT_API_KEY"
```

If a verb is missing from the remote policy, add it **before** applying gates.
Custom verbs are allowed via the API:

```bash
writ policy --key "$WRIT_API_KEY" --set <verb> <default_decision>
```

Allowed default decisions are typically `allow`, `deny`, `require_grant`.
Never invent a verb and hope the gate knows it — always verify with
`writ policy` first.

---

## 4. Show the planned diff and get explicit approval

`writ wrap` (or `writ scan --apply`) will insert a gate at the top of each
writing function:

```python
def issue_refund(charge_id, amount_cents):
    if _writ_check("payments.refund") != "ALLOW":
        raise PermissionError("writ denied payments.refund")
    ...
```

Preview the diff first:

```bash
writ wrap . --dry-run
```

`--diff-only` prints the unified diff and exits, which is useful for piping
into review tools. `writ scan .` without `--apply` prints the same diff.

Show the user the diff and ask for explicit approval:

> "Here is exactly what Writ will insert. Approve to apply?"

Do **not** apply without the user's explicit yes.

---

## 5. Apply the instrumentation

Once approved, use the guided command:

```bash
writ wrap .
```

`writ wrap` scans, shows the diff, prompts for explicit approval, applies the
gates per-file atomically, writes (or updates) `writ-policy.json`, and re-scans
reporting before/after coverage. For non-interactive environments such as CI,
use `--yes`:

```bash
writ wrap . --yes
```

The manual alternative is still available:

```bash
writ scan . --apply
```

Re-run the scan to confirm coverage:

```bash
writ scan .
```

Expected result: `gated: N/N (100%)` for the files the scanner can rewrite.
Remember to remind the user about the gaps section — those still need manual
review.

---

## 6. Verify: run a `writ_check` and confirm the audit log

Get a free API key if the user does not have one:

```bash
writ key --email user@example.com
```

Set the key and optional sponsor/agent metadata, then push the local policy to
the tenant:

```bash
export WRIT_API_KEY=writ_...
export WRIT_SPONSOR=acme
export WRIT_AGENT=support-agent

writ scan . --push-policy --key "$WRIT_API_KEY"
```

Run a live check against one of the gated verbs:

```bash
writ check --key "$WRIT_API_KEY" \
  --sponsor "$WRIT_SPONSOR" \
  --agent "$WRIT_AGENT" \
  --verb payments.refund \
  --target ch_123 \
  --purpose "customer refund"
```

Expected decision: `ALLOW`, `DENY`, or `STEP_UP`.

Confirm the decision appears in the audit log:

```bash
writ receipts --key "$WRIT_API_KEY"
```

Customer-facing explanation:

> "The check went through and the decision is now in your Writ audit log in the
> portal. You can also run `writ receipts` or `writ stream` to tail it from the
> CLI."

If you have the sponsor token, verify the kill switch works too:

```bash
writ revoke --sponsor "$WRIT_SPONSOR" --agent "$WRIT_AGENT" --reason "test"
writ reinstate --sponsor "$WRIT_SPONSOR" --agent "$WRIT_AGENT"
```

---

## MCP server alternative (for agents without shell access)

If the agent environment cannot run shell commands, use the **Writ MCP server**
instead. It exposes the same operations as 8 tools:

```bash
uvx writ-mcp==0.1.0
```

Tools available:

| Tool | Purpose |
|------|---------|
| `writ_check` | Gate a write and get `ALLOW` / `DENY` / `STEP_UP` |
| `writ_verify_token` | Validate an `ALLOW` auth token |
| `writ_grant` | Human-sponsor approval for `STEP_UP` |
| `writ_revoke` | Kill switch: revoke an agent/sponsor |
| `writ_reinstate` | Re-enable a revoked agent/sponsor |
| `writ_receipts` | Read the audit log (customer-facing: "audit log") |
| `writ_policy` | Get or set the tenant verb policy |
| `writ_sandbox` | Keyless trial — no API key needed |

Use `writ_policy` to list known verbs before mapping findings. Use `writ_check`
to verify a live decision, then `writ_receipts` to confirm it landed in the
audit log.

---

## Keyless trial with `writ_sandbox`

Users can try Writ before getting an API key. The `writ_sandbox` tool (MCP) or
the Python client method `client.sandbox(...)` issues a free 90-second demo
grant. It only allows the verb `demo_write` and targets starting with `demo-`.

Use this to demonstrate the gate end-to-end without asking for an email or API
key first:

```python
from pywrit import WritClient

client = WritClient()
result = client.sandbox({
    "sponsorId": "acme",
    "agentId": "agent-7",
    "verb": "demo_write",
    "target": "demo-customers",
    "purpose": "trying the gate",
})
print(result.decision)  # ALLOW
```

---

## Constraints checklist

- [ ] Never invent verbs the gate doesn't know — run `writ policy` first.
- [ ] Customer-facing language: **"audit log"**, not "receipts".
- [ ] No fake coverage claims — always mention the scanner's listed gaps.
- [ ] Always get explicit user approval before `writ scan . --apply` or `writ wrap .`.
- [ ] Prefer the guided `writ wrap .` flow; keep `writ scan . --apply` as the manual alternative.
- [ ] TS/JS scanning is scan-only; do not claim `--apply` or `writ wrap` rewrites TS/JS.
