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
        if manifest.exists():
            text = manifest.read_text()
            text = re.sub(r"writ-mcp==[^\s]+", f"writ-mcp=={VERSION}", text, count=1)
            # Also update the source URL in case the org changed.
            text = text.replace("AvenueDAdmin/pywrit", "withwrit/pywrit")
        else:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            text = f"""# Nous-approved MCP catalog entry.
# Presence in this directory = approval. Merged via PR review.
manifest_version: 1

name: writ
description: >-
  Commit-time policy checks for AI agent writes: ALLOW, DENY, or STEP_UP
  decisions, with an audit receipt for every outcome.
source: https://github.com/withwrit/pywrit

# PyPI-installed stdio server. Hermes spawns `uvx` with an exact version pin
# (required by the catalog's version-lock CI check); uvx fetches and runs the
# writ-mcp package on demand — no manual install step for the user.
transport:
  type: stdio
  command: uvx
  args:
    - writ-mcp=={VERSION}
  env:
    WRIT_API_KEY: "${{WRIT_API_KEY}}"
    WRIT_SPONSOR_TOKEN: "${{WRIT_SPONSOR_TOKEN}}"

auth:
  type: api_key
  env:
    - name: WRIT_API_KEY
      prompt: "Writ API key (starts with writ_ — free: POST /v1/keys with an email)"
      required: true
    - name: WRIT_SPONSOR_TOKEN
      prompt: "Writ sponsor token (only needed for sponsor tools: grant, revoke, reinstate)"
      required: false

# Composer-suggestion triggers (desktop brand pills).
suggest:
  keywords:
    - writ
    - audit log
    - policy check
    - guardrails
  hosts:
    - withwrit.com
  examples:
    - "Check a payment with Writ before sending it"
    - "Show recent Writ audit receipts"

post_install: |
  Get a free API key: POST /v1/keys with an email (quickstart at
  withwrit.com/docs). Or try it keyless first — the writ_sandbox tool
  issues a free 90-second demo grant with no key needed.

  The sponsor token is only required for writ_grant / writ_revoke /
  writ_reinstate. Restart the session so tools load.
"""
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

    # punkpeye README entry format — all three are enforced by repo bots:
    #   * name-check:  full `owner/repo` as the link text
    #   * glama-check: Glama score badge right after the repo link
    #                  (the server must be listed on Glama for it to resolve;
    #                   submit at https://glama.ai/mcp/servers if missing)
    #   * emoji-check: at least one permitted emoji after the link
    #                  (python stdio server, runs locally)
    bullet = (
        f"- [withwrit/pywrit]({REPO_URL}) "
        "[![withwrit/writ-mcp MCP server]"
        "(https://glama.ai/mcp/servers/withwrit/writ-mcp/badges/score.svg)]"
        "(https://glama.ai/mcp/servers/withwrit/writ-mcp) "
        "🐍 🏠 - "
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
        # Insert as the first entry UNDER the Security header. (The previous
        # code prepended the bullet before the header line, which landed the
        # entry at the end of the preceding section — the first PR ended up
        # under Research instead of Security.)
        new_text, subs = re.subn(
            r"^(###\s*🔒\s*<a name=\"security\"></a>Security)\n",
            r"\1\n" + bullet,
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if subs != 1:
            print("::error::Could not find Security section in punkpeye README")
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
                f"Add [withwrit/pywrit]({REPO_URL}) to the Security section.\n\n"
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
