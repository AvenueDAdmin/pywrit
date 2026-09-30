"""LangGraph agent whose refund tool is gated by the Writ permission gate.

The graph drives the real LangGraph tool-call path: a node emits an
``AIMessage`` with a ``tool_calls`` entry and LangGraph's ``ToolNode``
executes the ``issue_refund`` tool. The tool asks the Writ gate
(``POST /v1/check``) *before* touching the ledger:

* ``ALLOW``  -> the refund is recorded and a receipt id is returned.
* ``DENY`` / ``STEP_UP`` -> the write is blocked; the denial (with the
  audit receipt id) comes back as the tool result so the agent can react.

Run the demo against the live gate::

    export WRIT_API_KEY=writ_...
    python refund_agent.py
"""

from __future__ import annotations

from typing import Annotated, Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from writ_gate import WritDenied, WritGate

# Demo backend. In a real integration this is your payments/ledger system —
# the point is the gate sits between the agent's tool call and the write.
LEDGER: Dict[str, Dict[str, Any]] = {}


def make_issue_refund(gate: WritGate):
    """Build the ``issue_refund`` tool bound to a Writ gate."""

    @tool
    def issue_refund(order_id: str, amount_usd: float, reason: str) -> str:
        """Issue a USD refund for an order.

        Asks the Writ permission gate before writing. Blocked unless ALLOW.
        """
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

    return issue_refund


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    order_id: str
    amount_usd: float
    reason: str


def build_graph(gate: WritGate):
    """Graph: request_refund -> ToolNode(issue_refund) -> END."""
    issue_refund = make_issue_refund(gate)

    def request_refund(state: AgentState):
        # In production an LLM emits this tool call. Here we drive the same
        # LangGraph tool-call path directly: AIMessage w/ tool_calls -> ToolNode.
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "issue_refund",
                            "args": {
                                "order_id": state["order_id"],
                                "amount_usd": state["amount_usd"],
                                "reason": state["reason"],
                            },
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    graph = StateGraph(AgentState)
    graph.add_node("request_refund", request_refund)
    # handle_tool_errors=True: a gate denial (WritDenied) becomes an error
    # ToolMessage instead of crashing the graph, so the agent sees the
    # denial and can react to it.
    graph.add_node("tools", ToolNode([issue_refund], handle_tool_errors=True))
    graph.add_edge(START, "request_refund")
    graph.add_edge("request_refund", "tools")
    graph.add_edge("tools", END)
    return graph.compile()


def main() -> None:
    import os

    if not os.environ.get("WRIT_API_KEY"):
        raise SystemExit("Set WRIT_API_KEY to run the live demo.")
    LEDGER.clear()
    app = build_graph(WritGate())
    result = app.invoke(
        {
            "messages": [],
            "order_id": "order_123",
            "amount_usd": 42.50,
            "reason": "duplicate charge",
        }
    )
    for message in result["messages"]:
        print(f"{message.type}: {message.content}")
    print("ledger:", LEDGER)


if __name__ == "__main__":
    main()
