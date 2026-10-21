"""SQLite event store for validated read-only token observations."""
import json
import sqlite3
from pathlib import Path

from .risk import RiskScreen
from .scanner import TokenCreated


class TokenEventStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS token_creations (
                mint TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                creator TEXT NOT NULL,
                signature TEXT,
                observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS token_quality_annotations (
                mint TEXT PRIMARY KEY REFERENCES token_creations(mint),
                accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
                reasons_json TEXT NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.connection.commit()

    def insert(self, event: TokenCreated, *, quality: RiskScreen | None = None) -> bool:
        """Atomically insert the first observation and optional metadata-quality flag.

        Replays can backfill missing flags but never replace first-seen values.
        This is not a fraud detector or a trading safety assessment.
        """
        with self.connection:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO token_creations
                   (mint, name, symbol, creator, signature)
                   VALUES (?, ?, ?, ?, ?)""",
                (event.mint, event.name, event.symbol, event.creator, event.signature),
            )
            inserted = cursor.rowcount == 1
            if quality is not None:
                self.connection.execute(
                    """INSERT OR IGNORE INTO token_quality_annotations
                       (mint, accepted, reasons_json) VALUES (?, ?, ?)""",
                    (event.mint, int(quality.accepted), json.dumps(quality.reasons)),
                )
        return inserted

    def get_quality(self, mint: str) -> RiskScreen | None:
        """Return stored metadata-quality annotation, or None if absent."""
        row = self.connection.execute(
            "SELECT accepted, reasons_json FROM token_quality_annotations WHERE mint = ?",
            (mint,),
        ).fetchone()
        if row is None:
            return None
        return RiskScreen(accepted=bool(row[0]), reasons=tuple(json.loads(row[1])))

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) FROM token_creations").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
