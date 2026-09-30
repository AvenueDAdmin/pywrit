"""OpenAI Agents SDK function tool gated by the Writ permission gate.

``issue_refund`` is a standard ``@function_tool``. Before writing to
the ledger it asks the Writ gate (``POST /v1/check``), using the
``WritGate`` carried on the run context:

* ``ALLOW``  -> the refund is recorded; the audit receipt id is returned.
* ``DENY`` / ``STEP_UP`` -> ``WritDenied`` is raised, the write never
  happens, and the SDK surfaces the denial (with the audit receipt id)
  as the tool result so the agent can react.

Wire it into an agent with ``Agent(tools=[issue_refund])`` and pass the
gate via ``Runner.run(agent, input, context={"gate": WritGate()})``.
A full ``Runner.run`` needs an ``OPENAI_API_KEY``; the test below
exercises the real SDK tool-call path (``FunctionTool.on_invoke_tool``
with JSON arg parsing against the tool's schema) without one.

Run the demo against the live gate::

    export WRIT_API_KEY=writ_...
    python refund_tool.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from agents import RunContextWrapper, function_tool
from agents.tool_context import ToolContext

from writ_gate import WritDenied, WritGate

# Demo backend. In a real integration this is your payments/ledger system —
# the point is the gate sits between the agent's tool call and the write.
LEDGER: Dict[str, Dict[str, Any]] = {}


@function_tool
def issue_refund(
    ctx: RunContextWrapper[Dict[str, Any]],
    order_id: str,
    amount_usd: float,
    reason: str,
) -> str:
    """Issue a USD refund for an order.

    Asks the Writ permission gate before writing; blocked unless ALLOW.
    Expects ``ctx.context["gate"]`` to be a ``WritGate``.
    """
    gate: WritGate = ctx.context["gate"]
    receipt_id = gate.guard(
        verb="refund.issue",
        target=f"order:{order_id}",
        purpose=f"Refund ${amount_usd:.2f} for order {order_id}: {reason}",
    )
    LEDGER[order_id] = {
        "amount_usd": amount_usd,
        "reason": reason,
        "receipt_id": receipt_id,
    }
    return f"Refunded ${amount_usd:.2f} for order {order_id} (audit receipt {receipt_id})."


def make_context(gate: WritGate, args: Dict[str, Any]) -> ToolContext:
    """Build the real SDK tool-call context, as the Runner would."""
    raw = json.dumps(args)
    return ToolContext(
        context={"gate": gate},
        tool_name="issue_refund",
        tool_call_id="call_1",
        tool_arguments=raw,
    )


def main() -> None:
    import os

    if not os.environ.get("WRIT_API_KEY"):
        raise SystemExit("Set WRIT_API_KEY to run the live demo.")
    LEDGER.clear()

    async def run() -> None:
        gate = WritGate()
        args = {"order_id": "order_123", "amount_usd": 42.50, "reason": "duplicate charge"}
        # The real SDK tool-call path: JSON args -> schema validation -> tool.
        out = await issue_refund.on_invoke_tool(make_context(gate, args), json.dumps(args))
        print(out)

    asyncio.run(run())
    print("ledger:", LEDGER)


if __name__ == "__main__":
    main()
