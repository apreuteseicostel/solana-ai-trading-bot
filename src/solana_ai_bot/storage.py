"""SQLite event store for validated read-only token observations."""
import sqlite3
from pathlib import Path

from .scanner import TokenCreated


class TokenEventStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
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
        self.connection.commit()

    def insert(self, event: TokenCreated) -> bool:
        """Insert once per mint. Returns True for a newly inserted event."""
        with self.connection:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO token_creations
                   (mint, name, symbol, creator, signature)
                   VALUES (?, ?, ?, ?, ?)""",
                (event.mint, event.name, event.symbol, event.creator, event.signature),
            )
        return cursor.rowcount == 1

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) FROM token_creations").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
