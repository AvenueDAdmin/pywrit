"""Minimal Writ permission gate for agent tool calls.

Asks the Writ gate (https://api.withwrit.com) whether a write is allowed
*before* the tool performs it. Every decision is written to the gate's
tamper-evident audit log with a receipt id.

Only an ``ALLOW`` decision lets the write proceed. ``DENY`` and
``STEP_UP`` both block it — ``STEP_UP`` means a human sponsor must
approve out of band before the agent retries.
"""

from __future__ import annotations

import os
from typing import Optional

from pywrit import WritClient

PUBLIC_GATE_URL = "https://api.withwrit.com"


class WritDenied(Exception):
    """Raised when the gate does not ALLOW a write."""

    def __init__(self, decision: str, receipt_id: Optional[str], verb: str, target: str):
        self.decision = decision
        self.receipt_id = receipt_id
        super().__init__(
            f"Writ gate {decision}: verb={verb} target={target}"
            + (f" (audit receipt {receipt_id})" if receipt_id else "")
        )


class WritGate:
    """Guards tool calls behind ``POST /v1/check``."""

    def __init__(
        self,
        client: Optional[WritClient] = None,
        *,
        api_key: Optional[str] = None,
        base_url: str = PUBLIC_GATE_URL,
        sponsor_id: str = "example-sponsor",
        agent_id: str = "refund-agent",
    ):
        self.client = client or WritClient(
            api_key=api_key or os.environ.get("WRIT_API_KEY"),
            base_url=base_url,
        )
        self.sponsor_id = sponsor_id
        self.agent_id = agent_id

    def guard(self, verb: str, target: str, purpose: str) -> Optional[str]:
        """Ask the gate; return the audit receipt id.

        Raises :class:`WritDenied` unless the decision is ``ALLOW``.
        """
        result = self.client.check(
            sponsor_id=self.sponsor_id,
            agent_id=self.agent_id,
            verb=verb,
            target=target,
            purpose=purpose,
        )
        if not result.allowed:
            raise WritDenied(result.decision, result.receipt_id, verb, target)
        return result.receipt_id
