# Writ scan GitHub Action

Run the Writ scanner on every pull request. Each ungated write site the
scanner finds is posted as a check annotation on the exact file and line,
and the check fails when an ungated finding meets your risk threshold.

No API key needed — the scanner runs locally in the job and is free.

## Quick start

Copy [`examples/github-action/writ-scan.yml`](../examples/github-action/writ-scan.yml)
to `.github/workflows/writ-scan.yml` in your repo:

```yaml
name: Writ scan

on:
  pull_request:

permissions:
  contents: read

jobs:
  writ-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: AvenueDAdmin/pywrit@v0
        with:
          fail-on-risk: high
```

Open a PR that adds an ungated write — for example a `requests.post(...)`
to a notifications endpoint — and the check annotates the line and fails.

## What you get

- **Check annotations** on the PR's Files tab: one per ungated write site,
  at the file and line the scanner found.
- **A Markdown risk report** in the job summary: every finding with its
  risk tier, inferred verb (e.g. `notifications.send`), and function.
- **A threshold gate**: `fail-on-risk` decides which findings fail the
  check — `high` (default), `medium`, `low`, or `never` (report only).

Gated writes — functions that already call `writ_check(...)` — are never
annotated and never fail the check. That is the fix the action is nudging
toward: gate the write, and the annotation goes away.

## Inputs

| Input | Default | Description |
|---|---|---|
| `fail-on-risk` | `high` | Fail the check on ungated findings at or above this tier: `high`, `medium`, `low`, or `never`. |
| `path` | `.` | Repo-relative path to scan. |
| `exclude` | `""` | Comma- or newline-separated path substrings to skip. |
| `version` | `""` | Pin a pywrit version (default: latest from PyPI). |
| `polyglot` | `true` | Install `pywrit[polyglot]` for TypeScript/JavaScript scanning. Set `false` for Python-only repos. |
| `python-version` | `3.x` | Python version for the scan step. |

## Outputs

`ungated-high`, `ungated-medium`, `ungated-low` (finding counts) and
`failed` (`true` when the threshold was breached) — usable in later steps,
e.g. to post a PR comment or page on-call only for high-risk findings.

## How it works

The action installs `pywrit` from PyPI, runs
`writ scan --format json` (machine-readable risk report, read-only — no
files are modified), converts each ungated finding into a workflow-command
annotation (`::warning` below the threshold, `::error` at or above it),
and exits non-zero when the threshold is breached.

The scanner is heuristic: it finds ungated write sites in the patterns it
knows (see "What `writ scan` detects" in the README) and lists what it
cannot see in every report. It does not claim complete coverage — treat a
green check as "nothing found", not "nothing exists".

## Pairing with Semgrep

The scanner is the deep pass; a Semgrep ruleset makes a fast complementary
first pass in the same workflow. A draft 19-rule `writ-ungated-writes`
ruleset exists for agent-shaped Python repos — run it before the Writ step
so obvious ungated actions surface in seconds:

```yaml
- name: Semgrep quick pass
  run: |
    pip install semgrep
    semgrep --config <ruleset-url> --metrics=off --error .
```

(See the Semgrep sidecar notes for the ruleset status and the licensing
rule: never contribute these rules to `semgrep/semgrep-rules`.)
