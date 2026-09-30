#!/usr/bin/env python3
"""Tests for `writ scan --format json` (the GitHub Action's input).

Run with: python -m pytest tests/test_scan_json.py
"""

import argparse
import contextlib
import io
import json
import pathlib
import tempfile
import unittest

from pywrit import cli


def _args(path, **kw):
    ns = argparse.Namespace(path=str(path), exclude=[], policy_out="writ-policy.json",
                            apply=False, yes=False, score=False, push_policy=False,
                            key="", format="json")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _run_scan_json(root, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.scan_cmd(_args(root, **kw))
    return code, json.loads(buf.getvalue())


FIXTURE = '''\
import requests


def issue_refund(payment_id, amount_cents):
    """High risk: money movement, ungated."""
    resp = requests.post(
        "https://api.example.com/refunds",
        json={"payment": payment_id, "amount": amount_cents},
    )
    return resp.json()


def send_receipt(order_id, email):
    """Medium risk: outbound email, ungated."""
    import smtplib

    server = smtplib.SMTP("smtp.example.com")
    server.sendmail("noreply@example.com", [email], "receipt %s" % order_id)


def cancel_subscription(subscription_id):
    """Gated: already behind a writ gate, must not be reported."""
    if _writ_check("subscriptions.cancel", subscription_id,
                   "user requested cancellation") != "ALLOW":
        raise RuntimeError("denied")
    requests.post("https://api.example.com/subs/cancel",
                  json={"id": subscription_id})
'''

NOTIFY_FIXTURE = '''\
import smtplib


def send_receipt(order_id, email):
    """Medium risk: outbound email, ungated."""
    server = smtplib.SMTP("smtp.example.com")
    server.sendmail("noreply@example.com", [email], "receipt %s" % order_id)


def log_event(name):
    """Low risk: local append-only log, ungated."""
    with open("events.log", "a") as fh:
        fh.write(name + "\\n")
'''


class ScanJsonTest(unittest.TestCase):
    def _repo(self, td):
        root = pathlib.Path(td) / "repo"
        root.mkdir()
        (root / "billing.py").write_text(FIXTURE, encoding="utf-8")
        (root / "notify.py").write_text(NOTIFY_FIXTURE, encoding="utf-8")
        return root

    def test_json_document_shape(self):
        with tempfile.TemporaryDirectory() as td:
            code, doc = _run_scan_json(self._repo(td))
        self.assertEqual(code, 0)
        for key in ("scanner", "version", "root", "files_scanned",
                    "files_skipped", "findings"):
            self.assertIn(key, doc)
        self.assertEqual(doc["scanner"], "pywrit")
        self.assertGreaterEqual(len(doc["findings"]), 3)

    def test_finding_fields_and_risk_tiers(self):
        with tempfile.TemporaryDirectory() as td:
            _code, doc = _run_scan_json(self._repo(td))
        by_func = {f["function"]: f for f in doc["findings"]}
        for name in ("issue_refund", "send_receipt", "log_event",
                     "cancel_subscription"):
            self.assertIn(name, by_func, doc["findings"])
            for key in ("file", "line", "function", "verb", "risk", "gated",
                        "kind", "language", "snippet"):
                self.assertIn(key, by_func[name])
        # refunds are money movement -> high; email send -> medium;
        # local log append -> low
        self.assertEqual(by_func["issue_refund"]["risk"], "high")
        self.assertEqual(by_func["send_receipt"]["risk"], "medium")
        self.assertEqual(by_func["log_event"]["risk"], "low")
        # gated writes are flagged so the action can skip them
        self.assertTrue(by_func["cancel_subscription"]["gated"])
        self.assertFalse(by_func["issue_refund"]["gated"])
        self.assertEqual(by_func["issue_refund"]["file"], "billing.py")
        self.assertEqual(by_func["send_receipt"]["file"], "notify.py")
        for f in doc["findings"]:
            self.assertIsInstance(f["line"], int)
            self.assertGreater(f["line"], 0)

    def test_findings_sorted_high_first(self):
        with tempfile.TemporaryDirectory() as td:
            _code, doc = _run_scan_json(self._repo(td))
        order = {"high": 0, "medium": 1, "low": 2}
        tiers = [order[f["risk"]] for f in doc["findings"]]
        self.assertEqual(tiers, sorted(tiers))

    def test_json_is_read_only(self):
        # --format json must not write the policy file or anything else.
        with tempfile.TemporaryDirectory() as td:
            root = self._repo(td)
            code, _doc = _run_scan_json(root)
            self.assertEqual(code, 0)
            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                ["billing.py", "notify.py"])

    def test_empty_repo_gives_empty_findings(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "repo"
            root.mkdir()
            (root / "clean.py").write_text("X = 1\n", encoding="utf-8")
            code, doc = _run_scan_json(root)
        self.assertEqual(code, 0)
        self.assertEqual(doc["findings"], [])


if __name__ == "__main__":
    unittest.main()
