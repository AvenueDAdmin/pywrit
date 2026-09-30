"""Tests for the LangGraph + Writ refund agent.

* ``TestMockGate`` always runs: it stubs only the HTTP layer
  (``httpx.MockTransport``) so the real ``WritClient``, the real gate
  helper, and the real LangGraph tool-call path are all exercised.
* ``TestLiveGate`` runs against the live gate at
  https://api.withwrit.com when ``WRIT_API_KEY`` is set, and skips
  cleanly otherwise.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest
from langchain_core.messages import ToolMessage
from pywrit import WritClient

import refund_agent
from refund_agent import build_graph
from writ_gate import WritGate


def mock_writ_client(decision: str, receipt_id: str = "rcpt_test_1") -> WritClient:
    """A real WritClient whose HTTP layer returns a canned /v1/check verdict."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/check", request.url.path
        body = json.loads(request.content)
        assert body["verb"] == "refund.issue"
        return httpx.Response(
            200,
            json={
                "decision": decision,
                "receipt": {"receiptId": receipt_id},
                "receiptId": receipt_id,
                "authToken": "tok_test",
                "tokenExpiresIn": 300,
            },
        )

    return WritClient(
        api_key="writ_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def run_refund(gate: WritGate, order_id: str = "order_123"):
    refund_agent.LEDGER.clear()
    app = build_graph(gate)
    return app.invoke(
        {
            "messages": [],
            "order_id": order_id,
            "amount_usd": 42.50,
            "reason": "duplicate charge",
        }
    )


def tool_result(result) -> ToolMessage:
    msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(msgs) == 1, f"expected one tool result, got {len(msgs)}"
    return msgs[0]


class TestMockGate:
    def test_allow_records_refund(self):
        gate = WritGate(client=mock_writ_client("ALLOW"))
        msg = tool_result(run_refund(gate))

        assert msg.status == "success", msg.content
        assert "Refunded $42.50" in msg.content
        assert "rcpt_test_1" in msg.content
        assert refund_agent.LEDGER["order_123"]["amount_usd"] == 42.50
        assert refund_agent.LEDGER["order_123"]["receipt_id"] == "rcpt_test_1"

    def test_deny_blocks_refund(self):
        gate = WritGate(client=mock_writ_client("DENY", "rcpt_test_2"))
        msg = tool_result(run_refund(gate))

        # The write never happened; the denial comes back as the tool result.
        assert "order_123" not in refund_agent.LEDGER
        assert msg.status == "error", msg.content
        assert "DENY" in msg.content
        assert "rcpt_test_2" in msg.content

    def test_step_up_blocks_refund(self):
        gate = WritGate(client=mock_writ_client("STEP_UP", "rcpt_test_3"))
        msg = tool_result(run_refund(gate))

        assert "order_123" not in refund_agent.LEDGER
        assert "STEP_UP" in msg.content


@pytest.mark.skipif(
    not os.environ.get("WRIT_API_KEY"),
    reason="Set WRIT_API_KEY to run against the live gate (https://api.withwrit.com).",
)
class TestLiveGate:
    def test_live_gate_end_to_end(self):
        """Real /v1/check against the live gate, then the real graph.

        The tool's behavior must match the gate's verdict: an ALLOW
        records the refund, anything else leaves the ledger untouched.
        """
        gate = WritGate()  # reads WRIT_API_KEY from the environment
        probe = gate.client.check(
            sponsor_id=gate.sponsor_id,
            agent_id=gate.agent_id,
            verb="refund.issue",
            target="order:order_live_probe",
            purpose="Live integration test: consistency probe refund.",
        )

        msg = tool_result(run_refund(gate, order_id="order_live_1"))
        if probe.allowed:
            assert msg.status == "success", msg.content
            assert refund_agent.LEDGER["order_live_1"]["amount_usd"] == 42.50
        else:
            assert "order_live_1" not in refund_agent.LEDGER
            assert probe.decision in msg.content
