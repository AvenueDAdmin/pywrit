#!/usr/bin/env python3
"""Open/update catalog PRs for a new writ-mcp release.

Runs in GitHub Actions on v* tags. Expects:
  GH_TOKEN      PAT with repo + pull-request scopes for NousResearch and punkpeye orgs.
  VERSION       writ-mcp version (without leading v). If unset, reads from mcp/pyproject.toml.

What it does:
  1. Hermes (NousResearch/hermes-agent) — bumps the writ-mcp pin in
     optional-mcps/writ/manifest.yaml and opens a PR.
  2. punkpeye/awesome-mcp-servers — adds the Writ bullet under Security if it
     isn't already present and no PR is open.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOKEN = os.environ.get("GH_TOKEN", "")
VERSION = os.environ.get("VERSION", "")

HERMES_FORK = "withwrit/hermes-agent"
HERMES_UPSTREAM = "NousResearch/hermes-agent"
AWESOME_FORK = "withwrit/awesome-mcp-servers"
AWESOME_UPSTREAM = "punkpeye/awesome-mcp-servers"

REPO_URL = "https://github.com/withwrit/pywrit"
REGISTRY_NAME = "io.github.withwrit/writ"


def run(cmd, cwd=None, check=True):
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def gh(*args, _input=None, check=True):
    cmd = ["gh", *args]
    proc = subprocess.run(
        cmd,
        input=_input,
        text=True,
        capture_output=True,
        env={**os.environ, "GH_TOKEN": TOKEN},
    )
    if proc.returncode != 0 and check:
        print(proc.stderr, file=sys.stderr)
        proc.check_returncode()
    return proc.stdout.strip()


def clone(fork, dest):
    url = f"https://x-access-token:{TOKEN}@github.com/{fork}.git"
    run(["git", "clone", url, str(dest)])


def configure_git():
    run(["git", "config", "--global", "user.name", "Chad Dyar"])
    run(["git", "config", "--global", "user.email", "chad.dyar@gmail.com"])


def pr_exists(upstream, search):
    """Return the first matching PR number, or None."""
    out = gh(
        "pr", "list", "--repo", upstream,
        "--search", search,
        "--json", "number", "--jq", ".[0].number",
        check=False,
    )
    return out or None


def resolve_mcp_version():
    """Read writ-mcp version from mcp/pyproject.toml."""
    text = Path("mcp/pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        print("::error::Could not parse version from mcp/pyproject.toml")
        sys.exit(1)
    return m.group(1)


def open_hermes_pr():
    branch = f"bump-writ-mcp-{VERSION}"

    # Check for an existing PR from either the old or new org.
    existing = pr_exists(
        HERMES_UPSTREAM,
        f"is:pr is:open writ-mcp {VERSION} optional-mcps in:title",
    ) or pr_exists(
        HERMES_UPSTREAM,
        "is:pr is:open author:AvenueDAdmin writ optional-mcps",
    ) or pr_exists(
        HERMES_UPSTREAM,
        f"is:pr is:open author:withwrit writ-mcp {VERSION}",
    )
    if existing:
        print(f"Hermes PR already open: #{existing}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "hermes"
        clone(HERMES_FORK, dest)
        run(["git", "remote", "add", "upstream", f"https://github.com/{HERMES_UPSTREAM}.git"], cwd=dest)
        run(["git", "fetch", "upstream", "main"], cwd=dest)
        run(["git", "checkout", "-b", branch, "upstream/main"], cwd=dest)

        manifest = dest / "optional-mcps" / "writ" / "manifest.yaml"
        if not manifest.exists():
            print("::error::Hermes optional-mcps/writ/manifest.yaml not found")
            sys.exit(1)

        text = manifest.read_text()
        text = re.sub(r"writ-mcp==[^\s]+", f"writ-mcp=={VERSION}", text, count=1)
        manifest.write_text(text)

        run(["git", "add", "optional-mcps/writ/manifest.yaml"], cwd=dest)
        run(["git", "commit", "-m", f"bump(writ-mcp): {VERSION} in optional-mcps catalog"], cwd=dest)
        run(["git", "push", "-f", "-u", "origin", branch], cwd=dest)

        gh(
            "pr", "create", "--repo", HERMES_UPSTREAM,
            "--base", "main", "--head", f"{HERMES_FORK.split('/')[0]}:{branch}",
            "--title", f"bump(writ-mcp): {VERSION} in optional-mcps catalog",
            "--body", f"Updates the optional-mcps Writ manifest to pin `writ-mcp=={VERSION}`.",
        )
        print(f"Opened Hermes PR for writ-mcp {VERSION}")


def open_awesome_pr():
    branch = f"add-writ-mcp-{VERSION}"

    # If the entry is already in upstream README, nothing to do.
    try:
        raw_url = gh(
            "api", f"repos/{AWESOME_UPSTREAM}/contents/README.md",
            "--jq", ".download_url",
        )
        if raw_url:
            readme = run(["curl", "-sL", raw_url], check=False).stdout
            if "withwrit/pywrit" in readme or "AvenueDAdmin/pywrit" in readme:
                print("Writ entry already present in punkpeye/awesome-mcp-servers README; skipping.")
                return
    except subprocess.CalledProcessError:
        pass

    # If a PR from either org already exists, skip to avoid duplicates.
    existing = pr_exists(
        AWESOME_UPSTREAM,
        "is:pr is:open author:AvenueDAdmin writ MCP server",
    ) or pr_exists(
        AWESOME_UPSTREAM,
        "is:pr is:open author:withwrit writ MCP server",
    )
    if existing:
        print(f"punkpeye PR for Writ already open: #{existing}")
        return

    bullet = (
        f"- [writ]({REPO_URL}) - "
        "Commit-time policy checks for AI agent writes (ALLOW/DENY/STEP_UP) "
        "with a tamper-evident audit log. 8 tools via `uvx writ-mcp`.\n\n"
    )

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "awesome"
        clone(AWESOME_FORK, dest)
        run(["git", "remote", "add", "upstream", f"https://github.com/{AWESOME_UPSTREAM}.git"], cwd=dest)
        run(["git", "fetch", "upstream", "main"], cwd=dest)
        run(["git", "checkout", "-b", branch, "upstream/main"], cwd=dest)

        readme_path = dest / "README.md"
        text = readme_path.read_text()
        new_text, subs = re.subn(
            r"^(###\s*🌐\s*<a name=\"social-media\"></a>Social Media\n)",
            bullet + r"\1",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if subs != 1:
            print("::error::Could not find Social Media section in punkpeye README")
            sys.exit(1)
        readme_path.write_text(new_text)

        run(["git", "add", "README.md"], cwd=dest)
        run(["git", "commit", "-m", "Add writ MCP server to Security section"], cwd=dest)
        run(["git", "push", "-f", "-u", "origin", branch], cwd=dest)

        gh(
            "pr", "create", "--repo", AWESOME_UPSTREAM,
            "--base", "main", "--head", f"{AWESOME_FORK.split('/')[0]}:{branch}",
            "--title", "Add writ MCP server",
            "--body", (
                f"Add [writ]({REPO_URL}) to the Security section.\n\n"
                "- Commit-time policy checks for AI agent writes (ALLOW/DENY/STEP_UP) "
                "with a tamper-evident audit log.\n"
                "- 8 tools via `uvx writ-mcp`.\n"
                f"- Listed on the MCP Registry at `{REGISTRY_NAME}`."
            ),
        )
        print(f"Opened punkpeye PR for writ-mcp {VERSION}")


def main():
    if not TOKEN:
        print("::error::GH_TOKEN/CATALOG_PR_TOKEN secret is not set")
        sys.exit(1)

    global VERSION
    VERSION = VERSION or resolve_mcp_version()
    print(f"Using writ-mcp version: {VERSION}")

    configure_git()
    open_hermes_pr()
    open_awesome_pr()


if __name__ == "__main__":
    main()
