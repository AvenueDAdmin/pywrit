#!/usr/bin/env python3
"""Tests for `writ wrap`.

`writ wrap` is the single-verb path from scan to applied instrumentation.
It reuses the scan/plan helpers but adds approval, atomic apply, policy
update, and a re-scan coverage report.
"""

import argparse
import contextlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pywrit import cli  # noqa: E402

SAMPLE = '''\
import stripe


def issue_refund(charge_id, amount_cents):
    stripe.Refund.create(charge=charge_id, amount=amount_cents)
'''


def _wrap_args(path, **kw):
    ns = argparse.Namespace(
        path=str(path), exclude=[], policy="", dry_run=False,
        yes=False, diff_only=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _run_wrap(path, stdin_text=None, **kw):
    """Run wrap_cmd in-process; return (exit code, stdout)."""
    buf = io.StringIO()
    stdin = io.StringIO(stdin_text) if stdin_text is not None else sys.stdin
    with contextlib.redirect_stdout(buf):
        with patch.object(sys, "stdin", stdin):
            code = cli.wrap_cmd(_wrap_args(path, **kw))
    return code, buf.getvalue()


class WrapCommandTest(unittest.TestCase):
    def _make_repo(self, code=None):
        td = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(td))
        root = td / "repo"
        root.mkdir()
        (root / "payments.py").write_text(code or SAMPLE, encoding="utf-8")
        return root

    def _file_state(self, path):
        return (path.stat().st_mtime, path.read_text(encoding="utf-8"))

    def test_dry_run_leaves_files_and_policy_unchanged(self):
        root = self._make_repo()
        before = self._file_state(root / "payments.py")
        code, out = _run_wrap(root, dry_run=True)
        after = self._file_state(root / "payments.py")
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertFalse((root / "writ-policy.json").exists())
        self.assertIn("--dry-run", out)
        self.assertIn("payments.refund", out)

    def test_decline_with_default_n_makes_no_changes(self):
        root = self._make_repo()
        before = self._file_state(root / "payments.py")
        code, out = _run_wrap(root, stdin_text="\n")
        after = self._file_state(root / "payments.py")
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertFalse((root / "writ-policy.json").exists())
        self.assertIn("No changes made.", out)

    def test_approval_yes_applies_and_writes_policy(self):
        root = self._make_repo()
        code, out = _run_wrap(root, stdin_text="y\n")
        self.assertEqual(code, 0)
        self.assertIn("wrapped 1 gate(s)", out)
        self.assertIn("coverage: 0/1 -> 1/1 writes gated", out)
        self.assertTrue((root / "writ-policy.json").exists())
        policy = json.loads((root / "writ-policy.json").read_text())
        self.assertEqual(policy.get("payments.refund"), "require_grant")
        self.assertIn('if _writ_check("payments.refund")', out)
        self.assertIn("_writ_check", (root / "payments.py").read_text())

    def test_yes_flag_applies_without_prompt(self):
        root = self._make_repo()
        code, out = _run_wrap(root, yes=True)
        self.assertEqual(code, 0)
        self.assertIn("warning: approval was pre-granted", out)
        self.assertIn("wrapped 1 gate(s)", out)
        self.assertTrue((root / "payments.py").read_text().startswith(
            "import stripe\n\n# --- writ instrumentation"))

    def test_idempotent_second_wrap_changes_nothing(self):
        root = self._make_repo()
        _run_wrap(root, yes=True)
        first = (root / "payments.py").read_text(encoding="utf-8")
        code, out = _run_wrap(root, yes=True)
        second = (root / "payments.py").read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertEqual(first, second)
        self.assertIn("nothing to wrap.", out)

    def test_diff_only_prints_diff_and_exits_without_changes(self):
        root = self._make_repo()
        before = self._file_state(root / "payments.py")
        code, out = _run_wrap(root, diff_only=True)
        after = self._file_state(root / "payments.py")
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertFalse((root / "writ-policy.json").exists())
        self.assertIn("--- a/payments.py", out)
        self.assertIn("+++ b/payments.py", out)

    def test_no_write_sites_exits_one_quietly(self):
        td = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(td))
        root = td / "empty"
        root.mkdir()
        (root / "README.md").write_text("# empty", encoding="utf-8")
        code, out = _run_wrap(root)
        self.assertEqual(code, 1)
        self.assertIn("No write sites found.", out)

    def test_existing_policy_is_extended_not_overwritten(self):
        root = self._make_repo()
        (root / "policy.json").write_text(
            json.dumps({"orders.cancel": "require_grant"}) + "\n",
            encoding="utf-8")
        code, out = _run_wrap(root, policy=str(root / "policy.json"), yes=True)
        self.assertEqual(code, 0)
        policy = json.loads((root / "policy.json").read_text())
        self.assertEqual(policy["orders.cancel"], "require_grant")
        self.assertEqual(policy["payments.refund"], "require_grant")

    def test_partial_failure_does_not_corrupt_other_files(self):
        root = self._make_repo()
        (root / "orders.py").write_text(
            'def cancel_order(order_id):\n    db.execute("DELETE FROM orders")\n',
            encoding="utf-8")

        original_replace = os.replace
        calls = []

        def flaky_replace(src, dst):
            calls.append(dst)
            if "payments.py" in dst:
                raise OSError("simulated write failure")
            return original_replace(src, dst)

        code, out, err = None, "", ""
        with patch.object(cli.os, "replace", side_effect=flaky_replace):
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with contextlib.redirect_stdout(out_buf):
                with contextlib.redirect_stderr(err_buf):
                    code = cli.wrap_cmd(_wrap_args(root, yes=True))
            out = out_buf.getvalue()
            err = err_buf.getvalue()

        self.assertEqual(code, 2)
        self.assertIn("apply failed for 1 file(s)", err)
        # orders.py should be gated; payments.py should remain untouched.
        self.assertIn("_writ_check", (root / "orders.py").read_text())
        self.assertNotIn("_writ_check", (root / "payments.py").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
