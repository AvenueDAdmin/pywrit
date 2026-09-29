"""pywrit — Python client for Writ, the gate before the write.

Put a policy gate in front of your agent's dangerous actions:

    from pywrit import WritClient

    client = WritClient(api_key="writ_...")
    result = client.check(
        sponsor_id="acme",
        agent_id="agent-7",
        verb="db.write",
        target="prod.customers",
        purpose="backfill region field",
    )
    if result.decision == "ALLOW":
        ...  # perform the write, result.auth_token proves it was gated
    elif result.decision == "STEP_UP":
        ...  # a human sponsor must approve via client.grant(...)
"""

from .client import CheckResult, WritClient
from .errors import (
    AuthenticationError,
    NotFoundError,
    PaymentRequiredError,
    RateLimitError,
    WritError,
)

__version__ = "0.2.1"

__all__ = [
    "WritClient",
    "CheckResult",
    "WritError",
    "AuthenticationError",
    "PaymentRequiredError",
    "NotFoundError",
    "RateLimitError",
    "__version__",
]
