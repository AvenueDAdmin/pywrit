"""writ-mcp package tests — import-time checks only, no network."""

import asyncio

import writ_mcp
from writ_mcp import server

EXPECTED_TOOLS = {
    "writ_check",
    "writ_verify_token",
    "writ_grant",
    "writ_revoke",
    "writ_reinstate",
    "writ_receipts",
    "writ_policy",
    "writ_sandbox",
}


def test_version():
    assert writ_mcp.__version__ == "0.1.0"


def test_public_base_url_default():
    # The public package must never default to an internal endpoint.
    assert server.BASE_URL == "https://api.withwrit.com"
    assert "lambda-url" not in server.BASE_URL


def test_all_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_main_entrypoint_exists():
    assert callable(server.main)
