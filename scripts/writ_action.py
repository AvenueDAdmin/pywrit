#!/usr/bin/env python3
"""writ-scan GitHub Action runner.

Runs `writ scan --format json` on the checked-out repo, posts each ungated
write site as a check annotation (file/line), writes a Markdown risk report
to the job summary, and fails the step when an ungated finding meets or
exceeds the configured risk threshold.

Configuration comes from environment variables (set by action.yml):

    WRIT_FAIL_ON_RISK   high | medium | low | never   (default: high)
    WRIT_SCAN_PATH      repo-relative path to scan    (default: .)
    WRIT_EXCLUDE        comma- or newline-separated path substrings to skip
    GITHUB_WORKSPACE    used to re-base annotation paths to the repo root
    GITHUB_STEP_SUMMARY / GITHUB_OUTPUT  standard Actions files (optional)

Exit codes: 0 = scan clean (or below threshold), 1 = risk threshold breached,
2 = usage error or the scan itself failed.
"""

import json
import os
import shutil
import subprocess
import sys

SEVERITY = {"high": 0, "medium": 1, "low": 2}


def gh_escape(value):
    """Escape a workflow-command data/title value."""
    return (
        str(value)
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def annotate(level, rel_path, line, title, message):
    print(
        "::%s file=%s,line=%d,title=%s::%s"
        % (level, gh_escape(rel_path), line, gh_escape(title),
           gh_escape(message))
    )


def run_scan(scan_path, excludes):
    writ = shutil.which("writ")
    if writ:
        cmd = [writ]
    else:  # fall back to the module when only the package is importable
        cmd = [sys.executable, "-m", "pywrit.cli"]
    cmd += ["scan", "--format", "json", scan_path]
    for exc in excludes:
        cmd += ["--exclude", exc]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as err:
        print("::error::writ-scan: could not run the scanner: %s" % err)
        return None
    if proc.returncode != 0:
        print("::error::writ-scan: scanner exited %d: %s"
              % (proc.returncode, (proc.stderr or proc.stdout).strip()[:500]))
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        print("::error::writ-scan: could not parse scanner JSON: %s" % err)
        return None


def main():
    fail_on = os.environ.get("WRIT_FAIL_ON_RISK", "high").strip().lower()
    scan_path = os.environ.get("WRIT_SCAN_PATH", ".").strip() or "."
    raw_excludes = os.environ.get("WRIT_EXCLUDE", "")
    excludes = [e.strip() for e in raw_excludes.replace("\n", ",").split(",")
                if e.strip()]
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

    if fail_on not in ("high", "medium", "low", "never"):
        print("::error::writ-scan: invalid fail-on-risk %r "
              "(want high|medium|low|never)" % fail_on)
        return 2

    doc = run_scan(scan_path, excludes)
    if doc is None:
        return 2

    scan_root = os.path.realpath(doc.get("root") or scan_path)
    findings = doc.get("findings", [])
    ungated = [f for f in findings if not f.get("gated")]

    # Re-base annotation paths to the workspace root so they land on the
    # right file even when only a subdirectory was scanned.
    annotated = []
    for f in ungated:
        abs_path = os.path.realpath(os.path.join(scan_root, f["file"]))
        try:
            rel = os.path.relpath(abs_path, workspace)
        except ValueError:
            rel = f["file"]
        if rel.startswith(".."):
            rel = f["file"]
        annotated.append((rel, f))

    counts = {"high": 0, "medium": 0, "low": 0}
    for _rel, f in annotated:
        counts[f["risk"]] = counts.get(f["risk"], 0) + 1

    threshold = SEVERITY.get(fail_on)
    breached = []
    for rel, f in annotated:
        risk, verb = f["risk"], f["verb"]
        title = "Writ: ungated %s-risk write" % risk
        message = "Ungated %s-risk write: %s in %s()" % (
            risk, verb, f.get("function") or "<module>")
        if f.get("snippet"):
            message += " -- %s" % f["snippet"]
        if threshold is not None and SEVERITY[risk] <= threshold:
            breached.append(f)
            annotate("error", rel, f["line"], title, message)
        else:
            annotate("warning", rel, f["line"], title, message)

    write_summary(doc, annotated, counts, fail_on, breached)

    out_file = os.environ.get("GITHUB_OUTPUT")
    if out_file:
        with open(out_file, "a", encoding="utf-8") as fh:
            fh.write("ungated-high=%d\n" % counts["high"])
            fh.write("ungated-medium=%d\n" % counts["medium"])
            fh.write("ungated-low=%d\n" % counts["low"])
            fh.write("failed=%s\n" % ("true" if breached else "false"))

    if breached:
        print("::error::writ-scan: %d ungated write(s) at or above the "
              "'%s' risk threshold" % (len(breached), fail_on))
        return 1
    print("writ-scan: %d write site(s), %d ungated, threshold '%s' not "
          "breached" % (len(findings), len(ungated), fail_on))
    return 0


def write_summary(doc, annotated, counts, fail_on, breached):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    n_findings = len(doc.get("findings", []))
    lines = ["## Writ risk report", ""]
    lines.append(
        "Scanned %d file(s), found %d write site(s) "
        "(%d ungated)." % (doc.get("files_scanned", 0), n_findings,
                           len(annotated)))
    if doc.get("tsjs_hint"):
        lines.append("")
        lines.append("_TypeScript/JavaScript files were skipped: install the "
                     "scanner with the `polyglot` extra for TS/JS coverage._")
    lines.append("")
    lines.append("| Risk | File | Line | Verb | Function |")
    lines.append("| --- | --- | --- | --- | --- |")
    for rel, f in annotated:
        lines.append("| %s | `%s` | %d | `%s` | `%s()` |"
                    % (f["risk"], rel, f["line"], f["verb"],
                       f.get("function") or "<module>"))
    if not annotated:
        lines.append("| _none_ | | | | |")
    lines.append("")
    if breached:
        lines.append("**Check failed:** %d ungated write(s) at or above the "
                     "`%s` risk threshold." % (len(breached), fail_on))
    else:
        lines.append("Threshold `%s` not breached." % fail_on)
    lines.append("")
    lines.append("_The scanner finds ungated write sites; it does not claim "
                 "complete coverage. Review by hand for anything it misses._")
    lines.append("")
    try:
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
