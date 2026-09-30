# LangGraph + Writ: gate a refund tool

A minimal example of putting the [Writ](https://withwrit.com) permission
gate in front of a LangGraph tool that performs a write.

## How it works

`refund_agent.py` builds a small graph:

```
request_refund  ->  ToolNode(issue_refund)  ->  END
```

The `issue_refund` tool asks the Writ gate (`POST /v1/check`) **before**
writing to the ledger:

- `ALLOW` → the refund is recorded; the audit receipt id is returned.
- `DENY` / `STEP_UP` → the write is blocked; the denial (with the audit
  receipt id) comes back as the tool result so the agent can react.

Every decision is written to the gate's tamper-evident audit log.

## Run it

```bash
pip install -r requirements.txt
export WRIT_API_KEY=writ_...
python refund_agent.py
```

## Test it

```bash
pytest -v
```

- The mock-gate tests always run: they stub only the HTTP layer, so the
  real `WritClient`, the real gate helper, and the real LangGraph
  tool-call path (`AIMessage` with `tool_calls` → `ToolNode`) are all
  exercised. They prove an allowed write proceeds and a denied write is
  blocked.
- The live-gate test runs against `https://api.withwrit.com` when
  `WRIT_API_KEY` is set, and skips cleanly otherwise.
