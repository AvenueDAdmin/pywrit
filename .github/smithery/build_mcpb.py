"""Build the writ-mcp .mcpb bundle for the Smithery registry (stdio release).

Runs in CI on release tags. Probes the installed writ_mcp package over stdio
to capture the live tool schemas, then zips manifest.json + server.py +
requirements.txt + icon.png into writ-mcp.mcpb.

Env:
  WRIT_MCP_VERSION  Release version, e.g. "0.1.2" (tag without the leading v).
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path.cwd() / "writ-mcp.mcpb"

VERSION = os.environ.get("WRIT_MCP_VERSION", "").lstrip("v")
if not VERSION:
    raise SystemExit("WRIT_MCP_VERSION is not set")

DESCRIPTION = (
    "Writ \u2014 the gate before the write. Commit-time policy checks for AI agents: "
    "writ_check gates consequential writes (ALLOW / DENY / STEP_UP), writ_verify_token "
    "binds purpose-bound auth tokens, and every outcome writes a tamper-evident audit receipt."
)

USER_CONFIG = {
    "writ_api_key": {
        "type": "string",
        "title": "Writ API key",
        "description": "Your Writ API key (starts with writ_). Get one free, no credit card.",
        "required": True,
    },
    "writ_sponsor_token": {
        "type": "string",
        "title": "Sponsor token",
        "description": "Tenant sponsor token (writ_sp_...). Only needed for sponsor tools: writ_grant, writ_revoke, writ_reinstate.",
    },
    "writ_base_url": {
        "type": "string",
        "title": "Gate base URL",
        "description": "Defaults to the hosted Writ gate.",
        "default": "https://api.withwrit.com",
    },
}

SERVER_PY = '''"""Smithery bundle entry point: launch the writ-mcp server over stdio."""
import os

# Smithery injects configured values as env vars, using empty strings for
# unset optional fields. Drop empties so the server's built-in defaults apply.
for _var in ("WRIT_API_KEY", "WRIT_SPONSOR_TOKEN", "WRIT_BASE_URL"):
    if not os.environ.get(_var):
        os.environ.pop(_var, None)

from writ_mcp.server import main

main()
'''


def probe_tools():
    """Launch the installed writ_mcp server and capture its tools/list."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "from writ_mcp.server import main; main()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={k: v for k, v in os.environ.items()
             if k not in ("WRIT_API_KEY", "WRIT_SPONSOR_TOKEN", "WRIT_BASE_URL")},
    )

    def rpc(i, method, params=None):
        msg = {"jsonrpc": "2.0", "id": i, "method": method}
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read()
            raise RuntimeError(f"server produced no output; stderr: {err[:500]}")
        return json.loads(line)

    try:
        init = rpc(1, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "smithery-bundle-builder", "version": "1"},
        })
        assert "result" in init, f"initialize failed: {init}"
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        tools = rpc(2, "tools/list")
        assert "result" in tools, f"tools/list failed: {tools}"
        return tools["result"]["tools"]
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=15)


def main():
    tools = probe_tools()
    assert len(tools) == 8, f"expected 8 tools, got {len(tools)}: {[t['name'] for t in tools]}"
    print("tools:", [t["name"] for t in tools])

    icon_src = HERE / "icon.png"
    assert icon_src.exists(), "icon.png missing next to build_mcpb.py"

    manifest = {
        "manifest_version": "0.3",
        "name": "writ-mcp",
        "version": VERSION,
        "description": DESCRIPTION,
        "author": {"name": "Writ"},
        "homepage": "https://github.com/withwrit/pywrit",
        "repository": {"type": "git", "url": "https://github.com/withwrit/pywrit"},
        "license": "MIT",
        "icon": "icon.png",
        "server": {
            "type": "python",
            "entry_point": "server.py",
            "mcp_config": {
                "command": "python",
                "args": ["${__dirname}/server.py"],
                "env": {
                    "WRIT_API_KEY": "${user_config.writ_api_key}",
                    "WRIT_SPONSOR_TOKEN": "${user_config.writ_sponsor_token}",
                    "WRIT_BASE_URL": "${user_config.writ_base_url}",
                },
            },
        },
        "user_config": USER_CONFIG,
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
                **({"outputSchema": t["outputSchema"]} if t.get("outputSchema") else {}),
            }
            for t in tools
        ],
        "keywords": ["policy", "audit-log", "ai-agents", "authorization"],
        "compatibility": {"platforms": ["darwin", "linux", "win32"], "runtimes": {"python": ">=3.10"}},
    }

    build_dir = Path.cwd() / ".mcpb-build"
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True)
    (build_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (build_dir / "server.py").write_text(SERVER_PY)
    (build_dir / "requirements.txt").write_text(f"writ-mcp=={VERSION}\n")
    shutil.copy(icon_src, build_dir / "icon.png")

    # Validate before zipping.
    json.loads((build_dir / "manifest.json").read_text())
    compile((build_dir / "server.py").read_text(), "server.py", "exec")

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(build_dir.iterdir()):
            z.write(f, f.name)
    size = OUT.stat().st_size
    assert size < 25 * 1024 * 1024, "bundle exceeds Smithery's 25 MB limit"
    shutil.rmtree(build_dir, ignore_errors=True)
    print(f"bundle: {OUT} ({size} bytes), writ-mcp=={VERSION}")


if __name__ == "__main__":
    main()
