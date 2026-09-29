# pywrit

Python client + CLI for [Writ](https://withwrit.com) — the gate before the write.
Put a policy gate in front of your agent's dangerous actions.

## Install

```bash
pip install pywrit
```

## Python client

```python
from pywrit import WritClient

client = WritClient(api_key="writ_...")

result = client.check(
    sponsor_id="acme",
    agent_id="agent-7",
    verb="db.write",
    target="prod.customers",
    purpose="backfill region field",
)

if result.decision == "ALLOW":
    # result.auth_token is a short-lived token bound to this exact write
    perform_write(...)
elif result.decision == "STEP_UP":
    # a human sponsor must approve first: client.grant(...), then re-check
    ...
else:
    # DENY
    ...
```

No API key yet? Try the keyless sandbox:

```python
client = WritClient()
client.sandbox({
    "sponsorId": "acme",
    "agentId": "agent-7",
    "verb": "demo_write",       # sandbox only allows demo_write ...
    "target": "demo-customers", # ... on targets starting with demo-
    "purpose": "trying the gate",
})
```

### What's covered

- `check(...)` — the gate: `ALLOW` / `DENY` / `STEP_UP`, plus a receipt every time
- `verify_token(...)` — validate an `ALLOW` auth token (catches purpose drift)
- `grant(...)` — human-sponsor approval for the `STEP_UP` path
- `get_policy()` / `set_policy(...)` — manage the tenant policy
- `revoke(...)` / `reinstate(...)` / `revoked()` — the kill switch
- `receipts()` / `receipt(id)` / `verify_chain()` / `stream_receipts()` — the audit log
- `sandbox(...)` — keyless trial, no API key required

Every decision writes a receipt, so the audit log is the meter.

## CLI

The same package ships the `writ` command:

```bash
writ check --key writ_... --sponsor acme --agent agent-7 \
  --verb db.write --target prod.customers --purpose "backfill region field"
writ scan ./my-repo
writ receipts --key writ_...
writ verify-chain --key writ_...
```

Run `writ --help` for the full command list.

## Docs

Full API reference: [withwrit.com/docs](https://withwrit.com/docs)

## License

MIT
