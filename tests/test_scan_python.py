#!/usr/bin/env python3
"""Regression tests for Python write-site detection idioms.

Fixtures live in tests/fixtures/python_writes (one file per surface).
Run with: python -m pytest tests/test_scan_python.py
"""

import argparse
import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pywrit import cli  # noqa: E402

FIXTURES = HERE / "fixtures" / "python_writes"


def _args(path, **kw):
    ns = argparse.Namespace(
        path=str(path), exclude=[], policy_out="writ-policy.json",
        apply=False, yes=False, score=False, push_policy=False,
        key="", format="text")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _run_scan(path, **kw):
    """Run scan_cmd in-process; return (exit code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.scan_cmd(_args(path, **kw))
    return code, buf.getvalue()


def _copy_fixtures(dst):
    """Copy fixture .py files into dst (a directory)."""
    for p in FIXTURES.iterdir():
        if p.is_file() and p.suffix == ".py":
            shutil.copy(str(p), str(dst / p.name))


class PythonWritesTest(unittest.TestCase):
    def test_every_expected_idiom_is_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "repo"
            root.mkdir()
            _copy_fixtures(root)
            code, out = _run_scan(root, format="json")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        findings = doc["findings"]
        self.assertGreaterEqual(len(findings), 20, findings)
        kinds = {f["kind"] for f in findings}
        expected = {
            "payments", "sms", "http", "shell", "db", "k8s", "github",
            "push", "aws", "crypto", "docker", "ftp", "alert",
        }
        missing = expected - kinds
        self.assertFalse(missing, f"missing kinds {missing} in {findings}")
        # Every finding is ungated in the fixtures.
        self.assertTrue(all(not f["gated"] for f in findings))

    def test_score_is_numeric_and_moves_when_gated(self):
        ungated = '''\
import stripe


def refund_charge(charge_id, amount_cents):
    stripe.Refund.create(charge=charge_id, amount=amount_cents)
'''
        gated = '''\
import stripe


def refund_charge(charge_id, amount_cents):
    if _writ_check("payments.refund", str(charge_id), "refund") != "ALLOW":
        raise PermissionError("denied")
    stripe.Refund.create(charge=charge_id, amount=amount_cents)
'''
        with tempfile.TemporaryDirectory() as td:
            root_u = pathlib.Path(td) / "ungated"
            root_u.mkdir()
            (root_u / "payments.py").write_text(ungated, encoding="utf-8")
            _code, out_u = _run_scan(root_u, score=True)

            root_g = pathlib.Path(td) / "gated"
            root_g.mkdir()
            (root_g / "payments.py").write_text(gated, encoding="utf-8")
            _code, out_g = _run_scan(root_g, score=True)

        self.assertIn("Writ Score: 90/100", out_u)
        self.assertIn("Writ Score: 100/100", out_g)

    def test_ts_only_repo_is_unscored_not_fake_100(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "repo"
            root.mkdir()
            (root / "app.ts").write_text(
                'export function createOrder(u: string) {\n'
                '  fetch(u, { method: "POST" });\n}\n',
                encoding="utf-8")
            code, out = _run_scan(root)
        self.assertEqual(code, 0)
        self.assertIn("Writ Score: N/A", out)
        self.assertIn("No gradable Python writes were found", out)
        # Numeric score should not appear.
        self.assertNotIn("Writ Score: 100/100", out)

    def test_score_report_has_no_standalone_product_branding(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "repo"
            root.mkdir()
            _copy_fixtures(root)
            _code, out = _run_scan(root, score=True)
        self.assertIn("Writ Score:", out)
        self.assertNotIn("Fix this with Writ", out)
        self.assertNotIn("Scanner is free forever", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
