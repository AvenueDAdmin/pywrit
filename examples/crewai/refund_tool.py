"""CrewAI tool gated by the Writ permission gate.

``IssueRefundTool`` is a standard CrewAI ``BaseTool``. Its ``_run``
asks the Writ gate (``POST /v1/check``) *before* writing to the ledger:

* ``ALLOW``  -> the refund is recorded; the audit receipt id is returned.
* ``DENY`` / ``STEP_UP`` -> ``WritDenied`` is raised and the write never
  happens. In a crew run the agent sees the denial as the tool result.

Drop the tool into any CrewAI agent's ``tools=[...]`` list. A full
``crew.kickoff()`` needs an LLM API key; the test below exercises the
real CrewAI tool-call path (``tool.run(...)`` with args-schema
validation) without one.

Run the demo against the live gate::

    export WRIT_API_KEY=writ_...
    python refund_tool.py
"""

from __future__ import annotations

from typing import Any, Dict, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from writ_gate import WritGate

# Demo backend. In a real integration this is your payments/ledger system —
# the point is the gate sits between the agent's tool call and the write.
LEDGER: Dict[str, Dict[str, Any]] = {}


class RefundInput(BaseModel):
    order_id: str = Field(description="The order to refund, e.g. 'order_123'.")
    amount_usd: float = Field(description="Refund amount in USD.")
    reason: str = Field(description="Why the refund is being issued.")


class IssueRefundTool(BaseTool):
    name: str = "issue_refund"
    description: str = (
        "Issue a USD refund for an order. Asks the Writ permission gate "
        "before writing; blocked unless the gate returns ALLOW."
    )
    args_schema: Type[BaseModel] = RefundInput

    _gate: WritGate = PrivateAttr()

    def __init__(self, gate: WritGate, **kwargs):
        super().__init__(**kwargs)
        self._gate = gate

    def _run(self, order_id: str, amount_usd: float, reason: str) -> str:
        receipt_id = self._gate.guard(
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


def main() -> None:
    import os

    if not os.environ.get("WRIT_API_KEY"):
        raise SystemExit("Set WRIT_API_KEY to run the live demo.")
    LEDGER.clear()
    tool = IssueRefundTool(gate=WritGate())
    # The real CrewAI tool-call path: run() validates args, then calls _run().
    print(tool.run(order_id="order_123", amount_usd=42.50, reason="duplicate charge"))
    print("ledger:", LEDGER)


if __name__ == "__main__":
    main()
