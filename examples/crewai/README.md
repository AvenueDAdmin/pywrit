# CrewAI + Writ: gate a refund tool

A minimal example of putting the [Writ](https://withwrit.com) permission
gate in front of a CrewAI tool that performs a write.

## How it works

`refund_tool.py` defines `IssueRefundTool`, a standard CrewAI `BaseTool`.
Its `_run` asks the Writ gate (`POST /v1/check`) **before** writing to
the ledger:

- `ALLOW` → the refund is recorded; the audit receipt id is returned.
- `DENY` / `STEP_UP` → `WritDenied` is raised and the write never
  happens. In a crew run the agent sees the denial as the tool result.

Every decision is written to the gate's tamper-evident audit log. Drop
the tool into any CrewAI agent's `tools=[...]` list.

## Run it

```bash
pip install -r requirements.txt
export WRIT_API_KEY=writ_...
python refund_tool.py
```

(A full `crew.kickoff()` additionally needs an LLM API key.)

## Test it

```bash
pytest -v
```

- The mock-gate tests always run: they stub only the HTTP layer, so the
  real `WritClient`, the real gate helper, and the real CrewAI tool-call
  path (`tool.run(...)` with args-schema validation) are all exercised.
  They prove an allowed write proceeds and a denied write is blocked.
- The live-gate test runs against `https://api.withwrit.com` when
  `WRIT_API_KEY` is set, and skips cleanly otherwise.
