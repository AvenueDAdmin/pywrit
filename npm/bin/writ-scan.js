#!/usr/bin/env node
/**
 * writ-scan — run the Writ scanner (`writ scan`) without hand-installing Python packages.
 *
 * The scanner itself is Python (the `pywrit` package on PyPI). This shim:
 *   1. finds a Python 3.9+ interpreter,
 *   2. installs `pywrit[polyglot]` from PyPI on first run (skipped when already present),
 *   3. execs `writ scan` with your arguments, passing stdio and the exit code through.
 *
 * Why this approach: the scanner is a single Python package with prebuilt wheels
 * for its tree-sitter dependency, so a lazy `pip install` keeps the npm tarball
 * tiny (~10 KB) and always runs a released pywrit. Bundling a whole Python
 * runtime per OS/arch would bloat the package 1000x for no benefit here.
 * The tradeoff is that a Python 3.9+ interpreter must exist on the machine
 * (most dev machines already have one; Windows users may need python.org).
 *
 * Environment overrides:
 *   WRIT_PYTHON          explicit interpreter (default: auto-detect python3)
 *   WRIT_PYWRIT_SPEC     pip spec to install (default: pywrit[polyglot]==<pinned>)
 *   WRIT_SCAN_NO_INSTALL=1  never pip install; fail with instructions instead
 */

const { spawnSync } = require("node:child_process");

// Keep in lockstep with the pywrit release this npm version wraps.
const PYWRIT_VERSION = "0.2.5";
const PYWRIT_SPEC = process.env.WRIT_PYWRIT_SPEC || `pywrit[polyglot]==${PYWRIT_VERSION}`;

function fail(msg) {
  process.stderr.write(`writ-scan: error: ${msg}\n`);
  process.exit(1);
}

// Run a command, return { ok, stdout, stderr, status }.
function run(cmd, args, opts = {}) {
  try {
    const r = spawnSync(cmd, args, { encoding: "utf8", ...opts });
    return {
      ok: r.status === 0,
      stdout: (r.stdout || "").trim(),
      stderr: (r.stderr || "").trim(),
      status: r.status,
    };
  } catch (e) {
    return { ok: false, stdout: "", stderr: String(e && e.message || e), status: null };
  }
}

function findPython() {
  if (process.env.WRIT_PYTHON) return process.env.WRIT_PYTHON;
  const candidates =
    process.platform === "win32" ? ["py", "python", "python3"] : ["python3", "python"];
  for (const c of candidates) {
    const args = c === "py" ? ["-3"] : [];
    const r = run(c, [...args, "-c", "import sys; print(sys.version_info[0] * 100 + sys.version_info[1])"]);
    if (r.ok && /^\d+$/.test(r.stdout) && parseInt(r.stdout, 10) >= 309) {
      return c === "py" ? "py -3" : c;
    }
  }
  return null;
}

function splitCmd(python) {
  // "py -3" -> ["py", ["-3"]]; "python3" -> ["python3", []]
  const parts = python.split(" ");
  return [parts[0], parts.slice(1)];
}

function pywritStatus(python) {
  const [cmd, prefix] = splitCmd(python);
  const r = run(cmd, [...prefix, "-c", "import pywrit, tree_sitter; print(pywrit.__version__)"]);
  return r.ok ? r.stdout : null;
}

function pipInstall(python, extraArgs) {
  const [cmd, prefix] = splitCmd(python);
  const r = run(cmd, [...prefix, "-m", "pip", "install", "--quiet",
    "--disable-pip-version-check", ...extraArgs, PYWRIT_SPEC]);
  return r;
}

function ensurePywrit(python) {
  const have = pywritStatus(python);
  if (have === PYWRIT_VERSION) return;
  if (have) {
    process.stderr.write(
      `writ-scan: found pywrit ${have}, want ${PYWRIT_VERSION}; upgrading (one-time)...\n`);
  } else if (process.env.WRIT_SCAN_NO_INSTALL) {
    fail(
      "pywrit is not installed and WRIT_SCAN_NO_INSTALL=1.\n" +
      `  Install it yourself: ${python.split(" ")[0]} -m pip install '${PYWRIT_SPEC}'`
    );
  } else {
    process.stderr.write(
      `writ-scan: installing ${PYWRIT_SPEC} via pip (one-time, ~30s)...\n`);
  }

  const [cmd, prefix] = splitCmd(python);
  // Make sure pip itself exists.
  if (!run(cmd, [...prefix, "-m", "pip", "--version"]).ok) {
    const ep = run(cmd, [...prefix, "-m", "ensurepip", "--default-pip"]);
    if (!ep.ok) fail("pip is not available and ensurepip failed. Install pip, then re-run.");
  }

  // Fallback chain, from least to most invasive:
  //   1. plain install
  //   2. --user (permission-denied on system site-packages)
  //   3. --break-system-packages (PEP 668 externally-managed environments)
  //   4. --user --break-system-packages --ignore-installed
  //      (distro ships a dependency like typing_extensions without a RECORD
  //      file, so pip can't upgrade it in place; last resort is a shadowing
  //      copy in user site)
  const attempts = [
    [],
    ["--user"],
    ["--break-system-packages"],
    ["--user", "--break-system-packages", "--ignore-installed"],
  ];
  let r = null;
  for (const extra of attempts) {
    r = pipInstall(python, extra);
    if (r.ok) break;
  }
  if (!r.ok) {
    fail(
      `pip install failed:\n${r.stderr.split("\n").slice(-8).join("\n")}\n` +
      `  Try manually: ${python} -m pip install '${PYWRIT_SPEC}'`
    );
  }
  const now = pywritStatus(python);
  if (now !== PYWRIT_VERSION) {
    fail(`installed pywrit but found version '${now || "none"}' (want ${PYWRIT_VERSION}).`);
  }
  process.stderr.write(`writ-scan: pywrit ${PYWRIT_VERSION} ready.\n`);
}

function main() {
  const args = process.argv.slice(2);

  if (args.includes("--writ-shim-info")) {
    const python = findPython();
    const [cmd] = python ? splitCmd(python) : [null];
    const ver = python ? run(cmd, [...splitCmd(python)[1], "--version"]) : null;
    process.stdout.write(JSON.stringify({
      shim: "writ-scan",
      pywritPinned: PYWRIT_VERSION,
      python: python || null,
      pythonVersion: ver && ver.ok ? ver.stdout : null,
      pywritInstalled: python ? pywritStatus(python) : null,
      node: process.version,
    }, null, 2) + "\n");
    return;
  }

  const python = findPython();
  if (!python) {
    fail(
      "no Python 3.9+ found. The Writ scanner runs on Python.\n" +
      "  macOS/Linux: install python3 from your package manager or https://www.python.org/downloads/\n" +
      "  Windows: install from https://www.python.org/downloads/ (check 'Add python.exe to PATH')\n" +
      "  Then re-run. Or point WRIT_PYTHON at an interpreter."
    );
  }

  ensurePywrit(python);

  const [cmd, prefix] = splitCmd(python);
  const boot =
    "import sys; from pywrit.cli import main; " +
    "sys.argv[0] = 'writ'; raise SystemExit(main())";
  const r = spawnSync(cmd, [...prefix, "-c", boot, "scan", ...args], { stdio: "inherit" });
  process.exit(r.status === null ? 1 : r.status);
}

main();
