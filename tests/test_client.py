"""Tests for pywrit. Run with: python -m pytest"""

import json

import httpx

from pywrit import PaymentRequiredError, WritClient, WritError


def _client(handler):
    transport = httpx.MockTransport(handler)
    return WritClient(api_key="writ_test", http_client=httpx.Client(transport=transport))


def test_check_allow():
    def handler(request):
        assert request.url.path == "/v1/check"
        body = json.loads(request.content)
        assert body["verb"] == "db.write"
        return httpx.Response(
            200,
            json={
                "decision": "ALLOW",
                "receipt": {"receiptId": "r_123"},
                "authToken": "tok_abc",
                "tokenExpiresIn": 90,
            },
        )

    result = _client(handler).check("acme", "agent-7", "db.write", "prod.customers", "backfill")
    assert result.decision == "ALLOW"
    assert result.allowed
    assert result.receipt_id == "r_123"
    assert result.auth_token == "tok_abc"


def test_check_step_up():
    def handler(request):
        return httpx.Response(200, json={"decision": "STEP_UP", "receipt": {}})

    result = _client(handler).check("acme", "agent-7", "db.write", "prod.customers", "backfill")
    assert result.decision == "STEP_UP"
    assert not result.allowed


def test_payment_required():
    def handler(request):
        return httpx.Response(402, json={"portal_endpoint": "/v1/billing/portal"})

    try:
        _client(handler).check("acme", "agent-7", "db.write", "t", "p")
    except PaymentRequiredError as exc:
        assert exc.status_code == 402
        assert exc.portal_endpoint == "/v1/billing/portal"
    else:
        raise AssertionError("expected PaymentRequiredError")


def test_server_error():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    try:
        _client(handler).receipts()
    except WritError as exc:
        assert exc.status_code == 500
    else:
        raise AssertionError("expected WritError")


def test_verify_chain():
    def handler(request):
        assert request.url.path == "/v1/receipts/verify"
        return httpx.Response(200, json={"ok": True, "checked": 42, "complete": True})

    report = _client(handler).verify_chain()
    assert report["ok"] is True
    assert report["checked"] == 42


def test_cli_help():
    import io
    import sys
    from contextlib import redirect_stdout

    from pywrit.cli import main

    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["writ", "--help"]
    try:
        with redirect_stdout(buf):
            main()
    except SystemExit as exc:
        assert exc.code == 0
    finally:
        sys.argv = old
    assert "check" in buf.getvalue()
    assert "scan" in buf.getvalue()
