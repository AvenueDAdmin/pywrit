#!/usr/bin/env python3
"""Deterministic tests for `writ scan` TypeScript/JavaScript support.

Fixtures live in tests/fixtures/tsjs. Every line tagged `// expect: <rule>`
must be reported with that rule, and nothing else may be reported.
Tests that parse TS/JS skip when the optional `polyglot` extra
(tree-sitter) is not installed; the rest run with zero extra deps.
"""

import argparse
import contextlib
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pywrit import cli  # noqa: E402

FIXTURES = HERE / "fixtures" / "tsjs"
HAVE_EXTRA = bool(cli._tsjs_parsers())
_BLOCK_EXTRA = {m: None for m in ("tree_sitter", "tree_sitter_typescript",
                                  "tree_sitter_javascript",
                                  "tree_sitter_language_pack")}
_EXPECT = re.compile(r"//\s*expect:\s*([a-z0-9-]+)")
_FINDING = re.compile(
    r"^    (?P<file>\S+):(?P<line>\d+) \[(?P<kind>[a-z]+)\] "
    r"(?P<rule>[a-z0-9-]+) (?P<func>\S+)\(\): (?P<snippet>.+)$")


def _args(path, policy_out, **kw):
    ns = argparse.Namespace(path=str(path), exclude=[], policy_out=str(policy_out),
                            apply=False, yes=False, score=False, push_policy=False,
                            key="")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _run_scan(path, **kw):
    """Run scan_cmd in-process; return (exit code, stdout)."""
    with tempfile.TemporaryDirectory() as td:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.scan_cmd(_args(path, pathlib.Path(td) / "policy.json", **kw))
        return code, buf.getvalue()


def _expected():
    exp = set()
    for p in sorted(FIXTURES.rglob("*")):
        if p.suffix not in cli._TSJS_EXTS:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = _EXPECT.search(line)
            if m:
                exp.add((str(p.relative_to(FIXTURES)), i, m.group(1)))
    return exp


def _findings(out):
    return {(m.group("file"), int(m.group("line")), m.group("rule"))
            for m in map(_FINDING.match, out.splitlines()) if m}


def _copy_fixtures(dst):
    shutil.copytree(str(FIXTURES), str(dst))
    return dst


class FixtureRulesTest(unittest.TestCase):
    @unittest.skipUnless(HAVE_EXTRA, "polyglot extra not installed")
    def test_every_expected_finding_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as td:
            root = _copy_fixtures(pathlib.Path(td) / "repo")  # outside git
            code, out = _run_scan(root)
        self.assertEqual(code, 0)
        self.assertEqual(_findings(out), _expected(), out)

    def test_every_rule_has_a_fixture(self):
        covered = {r for (_f, _l, r) in _expected()}
        self.assertEqual(covered, {r[0] for r in cli._TSJS_RULES})

    @unittest.skipUnless(HAVE_EXTRA, "polyglot extra not installed")
    def test_negative_reads_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            shutil.copy(str(FIXTURES / "reads.tsx"), str(root / "reads.tsx"))
            code, out = _run_scan(root)
        self.assertEqual(code, 0)
        self.assertIn("ts/js files scanned: 1  skipped: 0", out)
        self.assertIn("ts/js write sites: 0 in 0 function(s)", out)
        self.assertEqual(_findings(out), set())
        self.assertIn("nothing to instrument.", out)

    @unittest.skipUnless(HAVE_EXTRA, "polyglot extra not installed")
    def test_output_format_counts_gating_and_verbs(self):
        with tempfile.TemporaryDirectory() as td:
            root = _copy_fixtures(pathlib.Path(td) / "repo")
            policy = pathlib.Path(td) / "p.json"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli.scan_cmd(_args(root, policy))
            out = buf.getvalue()
            verbs = __import__("json").loads(policy.read_text())
        self.assertEqual(code, 0)
        n = len(_expected())
        self.assertIn("ts/js files scanned: 7  skipped: 0  (scan only, no --apply)", out)
        self.assertIn("ts/js write sites: %d in 11 function(s)" % n, out)
        self.assertIn("ts/js gated: 1/%d" % n, out)  # gated.ts calls writCheck
        self.assertIn("    payments/refunds.service.ts:10 [sdk] stripe-write "
                      "issueRefund(): stripe.refunds.create({ charge: chargeId })", out)
        self.assertIn("    http.ts:10 [http] fetch-write createOrder(): fetch(url, "
                      "{ method: \"POST\", body: JSON.stringify(body) })", out)
        for v in ("payments.refund", "payments.record", "payments.export",
                  "storage.save", "storage.create", "http.create", "legacy.write"):
            self.assertEqual(verbs.get(v), "require_grant", v)
        self.assertIn("nothing to instrument (ts/js findings are scan-only", out)

    @unittest.skipUnless(HAVE_EXTRA, "polyglot extra not installed")
    def test_apply_never_rewrites_tsjs_but_still_gates_python(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "repo"
            (root / "orders").mkdir(parents=True)
            ts = root / "orders" / "api.ts"
            ts.write_text('export async function createOrder(u: string) {\n'
                          '  await fetch(u, { method: "POST" });\n}\n')
            py = root / "orders" / "store.py"
            py.write_text('def create_order():\n'
                          '    with open("/tmp/o", "w") as f:\n'
                          '        f.write("o")\n')
            before = ts.read_bytes()
            code, out = _run_scan(root, apply=True, yes=True)
            self.assertEqual(code, 0)
            self.assertEqual(ts.read_bytes(), before)
            self.assertIn("_writ_check(\"orders.create\")", py.read_text())
            self.assertIn("orders/api.ts:2 [http] fetch-write createOrder()", out)
            self.assertIn("applied 1 gate(s) to 1 file(s).", out)


class FileWalkTest(unittest.TestCase):
    """File collection is stdlib-only, so these run with or without the extra."""

    WRITE = 'export function f(){ return fetch("/x", { method: "POST" }); }\n'

    def _tree(self, root, rels):
        for rel in rels:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.WRITE)

    def test_skip_dirs_and_test_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            skipped = ["node_modules/pkg/index.js", "dist/app.js", "build/app.js",
                       ".next/server/page.js", ".git/hooks/x.js",
                       "vendor/lib.js", "venv/lib/x.js", ".venv/x.js",
                       "src/__tests__/a.ts", "tests/a.ts", "src/a.test.ts",
                       "src/a.spec.tsx", "types/a.d.ts", "public/app.min.js",
                       "src/readme.md", "src/a.py"]
            kept = ["src/a.ts", "src/b.tsx", "src/c.js", "src/d.jsx",
                    "src/e.mjs", "src/f.cjs", "lib/distance.ts"]
            self._tree(root, skipped + kept)
            got = [str(p.relative_to(root))
                   for p in cli._tsjs_collect_files(root, [])]
        self.assertEqual(sorted(got), sorted(kept))

    def test_exclude_substring(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            self._tree(root, ["src/a.ts", "generated/b.ts"])
            got = [str(p.relative_to(root))
                   for p in cli._tsjs_collect_files(root, ["generated"])]
        self.assertEqual(got, ["src/a.ts"])

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_respects_gitignore_inside_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("generated/\n*.gen.ts\n")
            self._tree(root, ["src/a.ts", "generated/b.ts", "src/c.gen.ts",
                              "node_modules/x/y.js"])
            got = [str(p.relative_to(root))
                   for p in cli._tsjs_collect_files(root, [])]
        self.assertEqual(got, ["src/a.ts"])


class MissingExtraTest(unittest.TestCase):
    def test_hint_once_and_python_still_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "web").mkdir()
            (root / "web" / "a.ts").write_text(FileWalkTest.WRITE)
            (root / "web" / "b.js").write_text(FileWalkTest.WRITE)
            (root / "orders.py").write_text(
                'def create_order(db):\n    db.execute("INSERT INTO o VALUES (1)")\n')
            with mock.patch.dict(sys.modules, _BLOCK_EXTRA):
                self.assertEqual(cli._tsjs_parsers(), {})
                code, out = _run_scan(root)
        self.assertEqual(code, 0)
        hints = [l for l in out.splitlines() if "hint:" in l]
        self.assertEqual(hints, ["  hint: 2 TS/JS file(s) not scanned; install "
                                 "the extra: pip install 'pywrit[polyglot]'"])
        self.assertIn("write sites: 1 in 1 function(s)", out)
        self.assertIn("orders.create", out)
        self.assertNotIn("ts/js files scanned", out)

    def test_python_only_repo_output_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "orders.py").write_text(
                'def create_order(db):\n    db.execute("INSERT INTO o VALUES (1)")\n')
            with mock.patch.dict(sys.modules, _BLOCK_EXTRA):
                code, out = _run_scan(root)
        self.assertEqual(code, 0)
        self.assertNotIn("hint:", out)
        self.assertNotIn("ts/js", out)
        self.assertTrue(out.startswith("writ scan: %s\n  files scanned: 1  skipped: 0\n"
                                       "  write sites: 1 in 1 function(s)\n"
                                       "  gated: 0/1 (0%%)\n  verbs discovered: 1\n"
                                       "    orders.create\n" % root.resolve()), out)


class CliSyncTest(unittest.TestCase):
    def test_download_copy_is_byte_identical(self):
        web = HERE.parent.parent / "gate" / "web" / "writ"
        if not web.exists():
            self.skipTest("gate/web/writ not present")
        self.assertEqual(web.read_bytes(),
                         (HERE.parent / "src" / "pywrit" / "cli.py").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
