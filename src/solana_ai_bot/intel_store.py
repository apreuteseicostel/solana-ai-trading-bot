"""Durable observations, quotes and atomic paper-book updates in SQLite."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .intel_models import Quote, WalletEvent


class IntelStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS wallet_events (
              wallet TEXT NOT NULL, signature TEXT NOT NULL, block_time INTEGER NOT NULL,
              observed_at INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(wallet,signature));
            CREATE INDEX IF NOT EXISTS wallet_event_time ON wallet_events(block_time);
            CREATE TABLE IF NOT EXISTS wallet_checkpoints (wallet TEXT PRIMARY KEY, signature TEXT);
            CREATE TABLE IF NOT EXISTS wallet_backfills (wallet TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_runs (
              id TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS copy_decisions (
              run_id TEXT NOT NULL, wallet TEXT NOT NULL, signature TEXT NOT NULL,
              payload TEXT NOT NULL, PRIMARY KEY(run_id,wallet,signature));
            CREATE TABLE IF NOT EXISTS market_quotes (
              id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS provider_requests (
              id INTEGER PRIMARY KEY, host TEXT NOT NULL, at INTEGER NOT NULL);
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def add_event(self, event: WalletEvent) -> int:
        return self.db.execute(
            "INSERT OR IGNORE INTO wallet_events VALUES (?,?,?,?,?)",
            (
                event.wallet,
                event.signature,
                event.block_time,
                event.observed_at,
                json.dumps(event.record(), sort_keys=True),
            ),
        ).rowcount

    def events(self, *, limit=10000):
        if not 1 <= limit <= 10000:
            raise ValueError("Event batch limit must be 1..10000")
        for row in self.db.execute(
            "SELECT payload FROM wallet_events ORDER BY block_time,signature LIMIT ?",
            (limit,),
        ):
            yield WalletEvent(**json.loads(row[0]))

    def pending(self, run_id, *, limit=1000, wallets=None):
        if not 1 <= limit <= 10000:
            raise ValueError("Event batch limit must be 1..10000")
        query = """SELECT e.payload FROM wallet_events e LEFT JOIN copy_decisions d
                   ON d.run_id=? AND d.wallet=e.wallet AND d.signature=e.signature
                   WHERE d.signature IS NULL"""
        params = [run_id]
        if wallets is not None:
            if not wallets:
                return []
            query += " AND e.wallet IN (" + ",".join("?" for _ in wallets) + ")"
            params.extend(wallets)
        query += " ORDER BY e.block_time,e.signature LIMIT ?"
        return [
            WalletEvent(**json.loads(row[0]))
            for row in self.db.execute(query, (*params, limit))
        ]

    def checkpoint(self, wallet):
        row = self.db.execute(
            "SELECT signature FROM wallet_checkpoints WHERE wallet=?", (wallet,)
        ).fetchone()
        return row[0] if row else None

    def set_checkpoint(self, wallet, signature):
        self.db.execute(
            "INSERT OR REPLACE INTO wallet_checkpoints VALUES (?,?)",
            (wallet, signature),
        )

    def backfill(self, wallet):
        row = self.db.execute(
            "SELECT payload FROM wallet_backfills WHERE wallet=?", (wallet,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_backfill(self, wallet, value):
        if value is None:
            self.db.execute("DELETE FROM wallet_backfills WHERE wallet=?", (wallet,))
        else:
            self.db.execute(
                "INSERT OR REPLACE INTO wallet_backfills VALUES (?,?)",
                (wallet, json.dumps(value)),
            )

    def add_quote(self, quote: Quote):
        self.db.execute(
            "INSERT INTO market_quotes(payload) VALUES (?)",
            (json.dumps(quote.record()),),
        )

    def run(self, run_id):
        row = self.db.execute(
            "SELECT config,state FROM paper_runs WHERE id=?", (run_id,)
        ).fetchone()
        return (json.loads(row[0]), json.loads(row[1])) if row else None

    def save_run(self, run_id, config, state):
        self.db.execute(
            "INSERT OR REPLACE INTO paper_runs VALUES (?,?,?)",
            (
                run_id,
                json.dumps(config, sort_keys=True),
                json.dumps(state, sort_keys=True),
            ),
        )

    def decision(self, run_id, event):
        row = self.db.execute(
            "SELECT payload FROM copy_decisions WHERE run_id=? AND wallet=? AND signature=?",
            (run_id, event.wallet, event.signature),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_decision(self, run_id, event, decision):
        self.db.execute(
            "INSERT INTO copy_decisions VALUES (?,?,?,?)",
            (
                run_id,
                event.wallet,
                event.signature,
                json.dumps(decision, sort_keys=True),
            ),
        )

    def decisions(self, run_id, limit=500):
        return [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT payload FROM copy_decisions WHERE run_id=? ORDER BY rowid DESC LIMIT ?",
                (run_id, limit),
            )
        ]

    def record_request(self, host, at):
        self.db.execute(
            "INSERT INTO provider_requests(host,at) VALUES (?,?)", (host, at)
        )

    def provider_usage(self):
        return {
            "scope": "whole_database_all_runs",
            "api_cost_usdc": None,
            "cost_status": "not_included_requires_provider_billing_data",
            "requests_by_host": {
                row[0]: row[1]
                for row in self.db.execute(
                    "SELECT host,COUNT(*) FROM provider_requests GROUP BY host"
                )
            },
        }
