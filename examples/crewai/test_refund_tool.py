"""Tests for the CrewAI + Writ refund tool.

* ``TestMockGate`` always runs: it stubs only the HTTP layer
  (``httpx.MockTransport``) so the real ``WritClient``, the real gate
  helper, and the real CrewAI tool-call path (``tool.run(...)`` with
  args-schema validation) are all exercised.
* ``TestLiveGate`` runs against the live gate at
  https://api.withwrit.com when ``WRIT_API_KEY`` is set, and skips
  cleanly otherwise.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest
from pywrit import WritClient

import refund_tool
from refund_tool import IssueRefundTool
from writ_gate import WritDenied, WritGate


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
    refund_tool.LEDGER.clear()
    tool = IssueRefundTool(gate=gate)
    return tool.run(order_id=order_id, amount_usd=42.50, reason="duplicate charge")


class TestMockGate:
    def test_allow_records_refund(self):
        out = run_refund(WritGate(client=mock_writ_client("ALLOW")))

        assert "Refunded $42.50" in out
        assert "rcpt_test_1" in out
        assert refund_tool.LEDGER["order_123"]["amount_usd"] == 42.50
        assert refund_tool.LEDGER["order_123"]["receipt_id"] == "rcpt_test_1"

    def test_deny_blocks_refund(self):
        with pytest.raises(WritDenied) as exc_info:
            run_refund(WritGate(client=mock_writ_client("DENY", "rcpt_test_2")))

        # The write never happened.
        assert "order_123" not in refund_tool.LEDGER
        assert exc_info.value.decision == "DENY"
        assert exc_info.value.receipt_id == "rcpt_test_2"

    def test_step_up_blocks_refund(self):
        with pytest.raises(WritDenied) as exc_info:
            run_refund(WritGate(client=mock_writ_client("STEP_UP", "rcpt_test_3")))

        assert "order_123" not in refund_tool.LEDGER
        assert exc_info.value.decision == "STEP_UP"


@pytest.mark.skipif(
    not os.environ.get("WRIT_API_KEY"),
    reason="Set WRIT_API_KEY to run against the live gate (https://api.withwrit.com).",
)
class TestLiveGate:
    def test_live_gate_end_to_end(self):
        """Real /v1/check against the live gate, then the real tool path.

        The tool's behavior must match the gate's verdict: an ALLOW
        records the refund, anything else raises and leaves the ledger
        untouched.
        """
        gate = WritGate()  # reads WRIT_API_KEY from the environment
        probe = gate.client.check(
            sponsor_id=gate.sponsor_id,
            agent_id=gate.agent_id,
            verb="refund.issue",
            target="order:order_live_probe",
            purpose="Live integration test: consistency probe refund.",
        )

        if probe.allowed:
            out = run_refund(gate, order_id="order_live_1")
            assert "Refunded $42.50" in out
            assert refund_tool.LEDGER["order_live_1"]["amount_usd"] == 42.50
        else:
            with pytest.raises(WritDenied) as exc_info:
                run_refund(gate, order_id="order_live_1")
            assert "order_live_1" not in refund_tool.LEDGER
            assert exc_info.value.decision == probe.decision
