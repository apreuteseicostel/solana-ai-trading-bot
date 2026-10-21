"""Offline API contract and safety tests; no provider or socket access."""

import io
import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from solana_ai_bot.copy_paper import CopyPaper
from solana_ai_bot.dashboard import handler_for, snapshot
from solana_ai_bot.intel_cli import demo
from solana_ai_bot.intel_store import IntelStore


class MemorySocket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = bytearray()

    def makefile(self, *_args):
        return self.input

    def sendall(self, data):
        self.output.extend(data)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "research.sqlite"
        with IntelStore(self.path) as store:
            self.now = demo(CopyPaper(store, "synthetic-demo"))

    def request(self, path="/api/snapshot", host="127.0.0.1:8765", extra="", method="GET"):
        connection = MemorySocket(
            f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n{extra}Connection: close\r\n\r\n".encode()
        )
        handler_for(self.path)(connection, ("127.0.0.1", 1234), SimpleNamespace(server_port=8765))
        headers, body = bytes(connection.output).split(b"\r\n\r\n", 1)
        return headers.decode(), body

    def test_snapshot_is_read_only_and_preserves_demo_provenance(self):
        before = self.path.read_bytes()
        result = snapshot(self.path, now=self.now)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(result["state"]["dataset_mode"], "synthetic_demo")
        self.assertFalse(result["live_execution_available"])
        self.assertEqual(len(result["recent_decisions"]), 3)
        self.assertEqual(result["collector_status"], "unknown_no_heartbeat_available")
        self.assertIsNone(result["provider_usage"]["api_cost_usdc"])

    def test_missing_database_is_not_created(self):
        path = Path(self.temp.name) / "missing.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            snapshot(path)
        self.assertFalse(path.exists())

    def test_unknown_run_does_not_create_one(self):
        with self.assertRaises(LookupError):
            snapshot(self.path, "not-present")
        with IntelStore(self.path) as store:
            self.assertIsNone(store.run("not-present"))

    def test_stale_or_future_marks_make_equity_unknown(self):
        with IntelStore(self.path) as store:
            config, state = store.run("synthetic-demo")
            state["positions"] = {"p": {"cost_raw": 100, "liquidation_raw": 120,
                                          "marked_at": self.now}}
            store.save_run("synthetic-demo", config, state)
        for at in (self.now - 1, self.now + config["max_quote_age_seconds"] + 1):
            result = snapshot(self.path, now=at)
            self.assertIsNone(result["equity_raw"])
            self.assertIsNone(result["unrealized_pnl_raw"])
        self.assertEqual(snapshot(self.path, now=self.now)["equity_raw"], state["cash_raw"] + 120)

    def test_response_caps_rows_and_isolates_run_decisions(self):
        with IntelStore(self.path) as store:
            CopyPaper(store, "other")
            for index in range(220):
                store.db.execute("INSERT INTO copy_decisions VALUES (?,?,?,?)", (
                    "synthetic-demo", "wallet", str(index), json.dumps({"signature": str(index)})))
        result = snapshot(self.path, "synthetic-demo", now=self.now)
        self.assertEqual(len(result["recent_decisions"]), 200)
        self.assertTrue(result["decisions_truncated"])
        self.assertEqual(snapshot(self.path, "other")["recent_decisions"], [])

    def test_api_contract_and_security_headers(self):
        headers, body = self.request()
        self.assertIn("200 OK", headers)
        self.assertIn("Cache-Control: no-store", headers)
        self.assertIn("frame-ancestors 'none'", headers)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertTrue(json.loads(body)["read_only"])

    def test_rebinding_cross_origin_and_write_requests_fail(self):
        for options in ({"host": "evil.example:8765"}, {"extra": "Origin: https://evil.example\r\n"}):
            self.assertIn("403", self.request(**options)[0])
        self.assertIn("501", self.request(method="POST")[0])

    def test_fixed_asset_allowlist_and_safe_error(self):
        for path in ("/../intel_store.py", "/api/snapshot?db=/etc/passwd", "/api/snapshot?run_id=a&run_id=b"):
            self.assertNotIn("200 OK", self.request(path)[0])
        headers, body = self.request("/api/snapshot?run_id=missing")
        self.assertIn("404", headers)
        self.assertNotIn(str(self.path).encode(), body)
        for path in ("/", "/styles.css", "/app.js"):
            self.assertIn("200 OK", self.request(path)[0])

    def test_ui_uses_text_nodes_for_untrusted_content(self):
        script = Path("src/solana_ai_bot/web/app.js").read_text()
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("eval(", script)
        self.assertIn("textContent", script)


if __name__ == "__main__":
    unittest.main()
