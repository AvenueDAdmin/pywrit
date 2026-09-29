"""Typed errors for the Writ API."""


class WritError(Exception):
    """Base error for Writ API failures."""

    def __init__(self, message, status_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AuthenticationError(WritError):
    """401 — missing or invalid API key."""


class PaymentRequiredError(WritError):
    """402 — free tier exhausted or billing past due. No receipt is written."""

    def __init__(self, message, status_code=None, body=None):
        super().__init__(message, status_code, body)
        self.portal_endpoint = (body or {}).get("portal_endpoint")


class NotFoundError(WritError):
    """404 — the requested resource does not exist."""


class RateLimitError(WritError):
    """429 — slow down and retry."""
