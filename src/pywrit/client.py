"""Synchronous Python client for the Writ gate API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

import httpx

from .errors import (
    AuthenticationError,
    NotFoundError,
    PaymentRequiredError,
    RateLimitError,
    WritError,
)

DEFAULT_BASE_URL = "https://api.withwrit.com"


@dataclass
class CheckResult:
    """The outcome of a gate check."""

    decision: str  # ALLOW | DENY | STEP_UP
    receipt: Dict[str, Any] = field(default_factory=dict)
    auth_token: Optional[str] = None
    token_expires_in: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"

    @property
    def receipt_id(self) -> Optional[str]:
        return self.receipt.get("receiptId") or self.raw.get("receiptId")


class WritClient:
    """Client for the Writ policy gate.

    Args:
        api_key: Your ``writ_`` API key. Not required for the keyless
            sandbox (``sandbox()``).
        base_url: Gate base URL. Defaults to the hosted gate.
        timeout: HTTP timeout in seconds.
        http_client: Optional pre-configured ``httpx.Client`` (useful for tests).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        http_client: Optional[httpx.Client] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = http_client or httpx.Client(timeout=timeout)

    # -- internals --------------------------------------------------------

    def _headers(self, authenticated: bool = True) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            if not self.api_key:
                raise AuthenticationError("An API key is required for this call.")
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, authenticated: bool = True, **kwargs) -> Any:
        try:
            resp = self._client.request(
                method, self.base_url + path, headers=self._headers(authenticated), **kwargs
            )
        except httpx.HTTPError as exc:
            raise WritError(f"Request failed: {exc}") from exc
        if resp.status_code == 401:
            raise AuthenticationError("Invalid or missing API key.", 401, _safe_json(resp))
        if resp.status_code == 402:
            raise PaymentRequiredError(
                "Free tier exhausted or billing past due — no receipt was written.",
                402,
                _safe_json(resp),
            )
        if resp.status_code == 404:
            raise NotFoundError("Not found.", 404, _safe_json(resp))
        if resp.status_code == 429:
            raise RateLimitError("Rate limited — slow down and retry.", 429, _safe_json(resp))
        if resp.status_code >= 400:
            body = _safe_json(resp)
            raise WritError(
                f"Writ API error {resp.status_code}: {body or resp.text}",
                resp.status_code,
                body,
            )
        if not resp.content:
            return None
        return resp.json()

    # -- the gate ----------------------------------------------------------

    def check(
        self,
        sponsor_id: str,
        agent_id: str,
        verb: str,
        target: str,
        purpose: str,
        ttl_seconds: Optional[int] = None,
    ) -> CheckResult:
        """Ask the gate whether an agent may perform a write.

        Returns a :class:`CheckResult` with ``decision`` of ``ALLOW``,
        ``DENY``, or ``STEP_UP``. On ``ALLOW`` the result also carries
        ``auth_token`` — a short-lived token bound to this exact
        sponsor/agent/verb/target/purpose. On ``STEP_UP`` a human sponsor
        must approve via :meth:`grant`, then the agent re-checks.
        """
        payload: Dict[str, Any] = {
            "sponsorId": sponsor_id,
            "agentId": agent_id,
            "verb": verb,
            "target": target,
            "purpose": purpose,
        }
        if ttl_seconds is not None:
            payload["ttlSeconds"] = ttl_seconds
        raw = self._request("POST", "/v1/check", json=payload)
        return CheckResult(
            decision=raw.get("decision", "DENY"),
            receipt=raw.get("receipt", {}),
            auth_token=raw.get("authToken"),
            token_expires_in=raw.get("tokenExpiresIn"),
            raw=raw,
        )

    def verify_token(
        self,
        token: str,
        verb: Optional[str] = None,
        target: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate an ``ALLOW`` auth token.

        When verb/target/purpose are given, the token must be bound to
        exactly that write — anything else is purpose drift and returns
        ``{"valid": False, ...}``.
        """
        payload: Dict[str, Any] = {"token": token}
        if verb is not None:
            payload["verb"] = verb
        if target is not None:
            payload["target"] = target
        if purpose is not None:
            payload["purpose"] = purpose
        return self._request("POST", "/v1/tokens/verify", json=payload)

    def grant(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mint a human-sponsor grant (the STEP_UP approval path)."""
        return self._request("POST", "/v1/grants", json=payload)

    # -- policy ------------------------------------------------------------

    def get_policy(self) -> Dict[str, Any]:
        """Fetch the tenant's current policy document."""
        return self._request("GET", "/v1/policy")

    def set_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the tenant's policy document."""
        return self._request("PUT", "/v1/policy", json=policy)

    # -- kill switch ---------------------------------------------------------

    def revoke(self, sponsor_id: str, agent_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Revoke an agent's ability to write."""
        return self._request(
            "POST", "/v1/revoke", json={"sponsorId": sponsor_id, "agentId": agent_id, **kwargs}
        )

    def reinstate(self, sponsor_id: str, agent_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Reinstate a previously revoked agent."""
        return self._request(
            "POST", "/v1/reinstate", json={"sponsorId": sponsor_id, "agentId": agent_id, **kwargs}
        )

    def revoked(self) -> List[Dict[str, Any]]:
        """List currently revoked agents."""
        return self._request("GET", "/v1/revoked")

    # -- audit log -----------------------------------------------------------

    def receipts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent receipts (the audit log)."""
        return self._request("GET", "/v1/receipts", params={"limit": limit})

    def receipt(self, receipt_id: str) -> Dict[str, Any]:
        """Fetch a single receipt by id."""
        return self._request("GET", f"/v1/receipts/{receipt_id}")

    def verify_chain(self, limit: int = 200) -> Dict[str, Any]:
        """Verify the tamper-evident audit-log hash chain.

        Recomputes every chained receipt's HMAC and checks each link.
        Returns ``{"ok": True, ...}`` when the chain is intact.
        """
        return self._request("GET", "/v1/receipts/verify", params={"limit": limit})

    def stream_receipts(self) -> Iterator[Dict[str, Any]]:
        """Yield receipts as they are written (server-sent events)."""
        with self._client.stream(
            "GET", self.base_url + "/v1/receipts/stream", headers=self._headers()
        ) as resp:
            if resp.status_code != 200:
                raise WritError(f"Stream failed: HTTP {resp.status_code}", resp.status_code)
            import json

            for line in resp.iter_lines():
                if line.startswith("data:"):
                    yield json.loads(line[5:].strip())

    # -- keyless trial ---------------------------------------------------------

    def sandbox(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run a check against the keyless sandbox. No API key required.

        The sandbox only allows verb ``demo_write`` and targets starting
        with ``demo-``. The payload needs ``sponsorId``, ``agentId``,
        ``verb``, ``target`` and ``purpose``.
        """
        return self._request("POST", "/v1/sandbox", authenticated=False, json=payload)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WritClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None
