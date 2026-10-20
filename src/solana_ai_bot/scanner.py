"""Read-only ingestion of PumpPortal-style new-token event messages.

No network access, order execution, or wallet functionality is provided here.
"""
import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


@dataclass(frozen=True)
class TokenCreated:
    mint: str
    name: str
    symbol: str
    creator: str
    signature: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def parse_token_creation(payload: Any) -> TokenCreated | None:
    """Accept only new-token-shaped records; reject malformed/unrelated messages."""
    if not isinstance(payload, dict):
        return None
    # PumpPortal create events normally contain mint, traderPublicKey, name, symbol.
    if payload.get("txType") not in (None, "create"):
        return None
    required = ("mint", "traderPublicKey")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        return None
    if any(len(payload[key]) > 256 for key in required):
        return None
    # Some provider creation messages omit the name and symbol metadata.
    # Preserve the creation event, leaving unknown metadata empty.
    name = payload.get("name", "")
    symbol = payload.get("symbol", "")
    if not isinstance(name, str) or not isinstance(symbol, str):
        return None
    if len(name) > 256 or len(symbol) > 256:
        return None
    signature = payload.get("signature")
    if signature is not None and (not isinstance(signature, str) or len(signature) > 256):
        return None
    return TokenCreated(
        mint=payload["mint"].strip(),
        name=name.strip(),
        symbol=symbol.strip(),
        creator=payload["traderPublicKey"].strip(),
        signature=signature,
    )


def read_events(lines: Iterable[str]) -> Iterable[TokenCreated]:
    """Yield distinct creation events using disk-backed mint deduplication.

    RAM no longer grows with the number of distinct mints; temporary disk
    usage does. Exhaust or close the iterator to release its temporary files.
    """
    with TemporaryDirectory(prefix="solana-mint-dedup-") as directory:
        with closing(sqlite3.connect(str(Path(directory) / "seen.sqlite"))) as db:
            db.execute("PRAGMA cache_size = -1024")
            db.execute("CREATE TABLE seen_mints (mint TEXT PRIMARY KEY)")
            for line in lines:
                try:
                    payload = json.loads(line)
                except (ValueError, TypeError):
                    continue
                event = parse_token_creation(payload)
                if event is None:
                    continue
                cursor = db.execute(
                    "INSERT OR IGNORE INTO seen_mints (mint) VALUES (?)",
                    (event.mint,),
                )
                if cursor.rowcount == 1:
                    yield event


def scan_file(source: Path, destination: Path) -> int:
    """Transform a local fixture/event stream into deduplicated JSONL."""
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output must differ")
    with source.open("r", encoding="utf-8") as input_stream:
        destination.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with destination.open("w", encoding="utf-8") as output_stream:
            for event in read_events(input_stream):
                output_stream.write(event.to_json() + "\n")
                count += 1
    return count
