"""Local read-only dashboard. No provider calls or database mutations."""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

MAX_ROWS = 200


def snapshot(database: Path, run_id: str | None = None, *, now: int | None = None):
    """Read a consistent bounded snapshot, opening SQLite in read-only mode."""
    now = int(time.time()) if now is None else now
    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        runs = [r[0] for r in db.execute("SELECT id FROM paper_runs ORDER BY id LIMIT 201")]
        if run_id is None and runs:
            run_id = runs[0]
        row = db.execute(
            "SELECT config,state FROM paper_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Paper run not found")
        config, state = json.loads(row[0]), json.loads(row[1])
        positions = state["positions"]
        fresh = all(
            p.get("liquidation_raw") is not None
            and p.get("marked_at") is not None
            and 0 <= now - p["marked_at"] <= config["max_quote_age_seconds"]
            for p in positions.values()
        )
        equity = state["cash_raw"] + sum(
            p["liquidation_raw"] for p in positions.values()
        ) if fresh else None
        decisions = [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM copy_decisions WHERE run_id=? ORDER BY rowid DESC LIMIT ?",
            (run_id, MAX_ROWS + 1),
        )]
        # Provenance is explicit: these observations span the database, not just this run.
        observations = [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM wallet_events ORDER BY observed_at DESC,signature LIMIT ?",
            (MAX_ROWS + 1,),
        )]
        usage = {r[0]: r[1] for r in db.execute(
            "SELECT host,COUNT(*) FROM provider_requests GROUP BY host LIMIT 20"
        )}
        latest = db.execute("SELECT MAX(observed_at) FROM wallet_events").fetchone()[0]
        return {
            "schema_version": 1, "generated_at": now, "read_only": True,
            "live_execution_available": False, "run_id": run_id,
            "runs": runs[:MAX_ROWS], "runs_truncated": len(runs) > MAX_ROWS,
            "config": config, "state": state, "equity_raw": equity,
            "unrealized_pnl_raw": None if equity is None else equity
            - state["cash_raw"] - sum(p["cost_raw"] for p in positions.values()),
            "equity_status": "fresh_quote_marks" if fresh else "unknown_stale_or_missing_marks",
            "recent_decisions": decisions[:MAX_ROWS],
            "decisions_truncated": len(decisions) > MAX_ROWS,
            "observations": observations[:MAX_ROWS],
            "observations_truncated": len(observations) > MAX_ROWS,
            "observation_scope": "whole_database_all_runs",
            "latest_observed_at": latest,
            "collector_status": "unknown_no_heartbeat_available",
            "provider_usage": {"scope": "whole_database_all_runs",
                               "requests_by_host": usage, "api_cost_usdc": None},
        }


def handler_for(database: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log request URLs, user content or query parameters.

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.respond(403, b'{"error":"Local host required"}', "application/json")
                return
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                self.respond(403, b'{"error":"Cross-origin request refused"}', "application/json")
                return
            target = urlsplit(self.path)
            if len(self.path) > 2048:
                self.respond(400, b'{"error":"Request too long"}', "application/json")
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css; charset=utf-8")}
            if target.path in assets:
                name, mime = assets[target.path]
                self.respond(200, files("solana_ai_bot").joinpath("web", name).read_bytes(), mime)
            elif target.path == "/api/snapshot":
                query = parse_qs(target.query)
                if set(query) - {"run_id"} or len(query.get("run_id", [])) > 1:
                    self.respond(400, b'{"error":"Invalid query"}', "application/json")
                    return
                try:
                    result = snapshot(database, query.get("run_id", [None])[0])
                    self.respond(200, json.dumps(result).encode(), "application/json")
                except LookupError:
                    self.respond(404, b'{"error":"No matching paper experiment"}', "application/json")
                except (sqlite3.Error, ValueError, KeyError, TypeError, OSError):
                    self.respond(503, b'{"error":"Snapshot unavailable; check database schema"}', "application/json")
            else:
                self.respond(404, b'{"error":"Not found"}', "application/json")

        def respond(self, status, content, mime):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                             "style-src 'self'; connect-src 'self'; img-src 'self'; "
                             "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(content)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local paper research dashboard; read-only")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--db", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be 1024..65535")
    with TemporaryDirectory(prefix="paper-dashboard-") as directory:
        database = args.db
        if args.demo:
            from .copy_paper import CopyPaper
            from .intel_cli import demo
            from .intel_store import IntelStore

            database = Path(directory) / "demo.sqlite"
            with IntelStore(database) as store:
                demo(CopyPaper(store, "synthetic-demo"))
        if not database.is_file():
            parser.error("Database does not exist; use --demo for synthetic data")
        with HTTPServer(("127.0.0.1", args.port), handler_for(database)) as server:
            print(f"Paper dashboard: http://127.0.0.1:{args.port} (local, read-only)")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
