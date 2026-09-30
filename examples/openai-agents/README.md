# OpenAI Agents SDK + Writ: gate a refund tool

A minimal example of putting the [Writ](https://withwrit.com) permission
gate in front of an OpenAI Agents SDK function tool that performs a write.

## How it works

`refund_tool.py` defines `issue_refund` with `@function_tool`. Before
writing to the ledger it asks the Writ gate (`POST /v1/check`), using
the `WritGate` carried on the run context:

- `ALLOW` → the refund is recorded; the audit receipt id is returned.
- `DENY` / `STEP_UP` → the write is blocked; the SDK surfaces the denial
  (with the audit receipt id) as the tool result so the agent can react.

Every decision is written to the gate's tamper-evident audit log. Wire
the tool into an agent with `Agent(tools=[issue_refund])` and pass the
gate via `Runner.run(agent, input, context={"gate": WritGate()})`.

## Run it

```bash
pip install -r requirements.txt
export WRIT_API_KEY=writ_...
python refund_tool.py
```

(A full `Runner.run` additionally needs an `OPENAI_API_KEY`.)

## Test it

```bash
pytest -v
```

- The mock-gate tests always run: they stub only the HTTP layer, so the
  real `WritClient`, the real gate helper, and the real SDK tool-call
  path (`FunctionTool.on_invoke_tool` with JSON arg parsing against the
  tool's schema) are all exercised. They prove an allowed write proceeds
  and a denied write is blocked.
- The live-gate test runs against `https://api.withwrit.com` when
  `WRIT_API_KEY` is set, and skips cleanly otherwise.
