"""Tests for the OpenAI Agents SDK + Writ refund tool.

* ``TestMockGate`` always runs: it stubs only the HTTP layer
  (``httpx.MockTransport``) so the real ``WritClient``, the real gate
  helper, and the real SDK tool-call path
  (``FunctionTool.on_invoke_tool`` with JSON arg parsing against the
  tool's schema) are all exercised.
* ``TestLiveGate`` runs against the live gate at
  https://api.withwrit.com when ``WRIT_API_KEY`` is set, and skips
  cleanly otherwise.
"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest
from pywrit import WritClient

import refund_tool
from refund_tool import issue_refund, make_context
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


def run_refund(gate: WritGate, order_id: str = "order_123") -> str:
    """Drive the real SDK tool-call path: JSON args -> schema -> tool."""
    refund_tool.LEDGER.clear()
    args = {"order_id": order_id, "amount_usd": 42.50, "reason": "duplicate charge"}
    return asyncio.run(
        issue_refund.on_invoke_tool(make_context(gate, args), json.dumps(args))
    )


class TestMockGate:
    def test_allow_records_refund(self):
        out = run_refund(WritGate(client=mock_writ_client("ALLOW")))

        assert "Refunded $42.50" in out
        assert "rcpt_test_1" in out
        assert refund_tool.LEDGER["order_123"]["amount_usd"] == 42.50
        assert refund_tool.LEDGER["order_123"]["receipt_id"] == "rcpt_test_1"

    def test_deny_blocks_refund(self):
        out = run_refund(WritGate(client=mock_writ_client("DENY", "rcpt_test_2")))

        # The write never happened; the denial (with the audit receipt id)
        # is what the agent sees as the tool result.
        assert "order_123" not in refund_tool.LEDGER
        assert "DENY" in out
        assert "rcpt_test_2" in out

    def test_step_up_blocks_refund(self):
        out = run_refund(WritGate(client=mock_writ_client("STEP_UP", "rcpt_test_3")))

        assert "order_123" not in refund_tool.LEDGER
        assert "STEP_UP" in out
        assert "rcpt_test_3" in out


@pytest.mark.skipif(
    not os.environ.get("WRIT_API_KEY"),
    reason="Set WRIT_API_KEY to run against the live gate (https://api.withwrit.com).",
)
class TestLiveGate:
    def test_live_gate_end_to_end(self):
        """Real /v1/check against the live gate, then the real tool path.

        The tool's behavior must match the gate's verdict: an ALLOW
        records the refund, anything else surfaces the denial and leaves
        the ledger untouched.
        """
        gate = WritGate()  # reads WRIT_API_KEY from the environment
        probe = gate.client.check(
            sponsor_id=gate.sponsor_id,
            agent_id=gate.agent_id,
            verb="refund.issue",
            target="order:order_live_probe",
            purpose="Live integration test: consistency probe refund.",
        )

        out = run_refund(gate, order_id="order_live_1")
        if probe.allowed:
            assert "Refunded $42.50" in out
            assert refund_tool.LEDGER["order_live_1"]["amount_usd"] == 42.50
        else:
            assert "order_live_1" not in refund_tool.LEDGER
            assert probe.decision in out
