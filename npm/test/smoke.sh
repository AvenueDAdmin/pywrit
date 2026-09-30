#!/usr/bin/env bash
# Install-test for the writ-scan npm package.
# Packs npm/, installs the tarball in a scratch dir, and runs `writ-scan`
# against the TS fixture. Expects real TS/JS write sites to be found.
set -euo pipefail

NPM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

echo "== npm pack =="
cd "$NPM_DIR"
TARBALL="$(npm pack --silent 2>/dev/null | tail -1)"
echo "packed: $TARBALL"

echo "== install tarball in scratch dir =="
mkdir -p "$SCRATCH/app"
cd "$SCRATCH/app"
npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund "$NPM_DIR/$TARBALL" >/dev/null 2>&1
BIN="$SCRATCH/app/node_modules/.bin/writ-scan"
test -x "$BIN" || { echo "FAIL: bin not installed"; exit 1; }
echo "bin installed: $BIN"

echo "== shim info =="
"$BIN" --writ-shim-info

echo "== first run (bootstraps pywrit via pip) =="
"$BIN" "$NPM_DIR/test/fixture" --policy-out "$SCRATCH/policy.json" 2>&1 | tee "$SCRATCH/out1.txt"

echo "== second run (cached, no reinstall) =="
"$BIN" "$NPM_DIR/test/fixture" --policy-out "$SCRATCH/policy.json" 2>&1 | tee "$SCRATCH/out2.txt"

echo "== assertions =="
grep -q "ts/js write sites: [5-9]" "$SCRATCH/out1.txt" \
  || { echo "FAIL: expected >=5 ts/js write sites"; cat "$SCRATCH/out1.txt"; exit 1; }
grep -q "installing pywrit" "$SCRATCH/out2.txt" \
  && { echo "FAIL: second run re-installed"; exit 1; }
test -f "$SCRATCH/policy.json" || { echo "FAIL: policy file not written"; exit 1; }

echo "PASS: writ-scan finds TS/JS write sites from a tarball install"
