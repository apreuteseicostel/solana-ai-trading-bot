"""Integration checks: the dashboard must not expose executable signals."""

from pathlib import Path

from solana_ai_bot.copy_paper import CopyPaper
from solana_ai_bot.dashboard import snapshot
from solana_ai_bot.intel_cli import demo
from solana_ai_bot.intel_store import IntelStore


def test_signal_dashboard_exposes_provenance_without_execution(tmp_path: Path):
    path = tmp_path / "demo.sqlite"
    with IntelStore(path) as store:
        when = demo(CopyPaper(store, "demo"))
    before = path.read_bytes()
    result = snapshot(path, "demo", now=when)

    assert result["read_only"] is True
    assert result["live_execution_available"] is False
    assert result["signal_feed_type"] == "retrospective_paper_decisions_not_live_alerts"
    assert result["paper_auto"] == {
        "mode": "bounded_cli_session_only",
        "service_status": "unknown_no_heartbeat",
        "dashboard_control": False,
        "execution": "paper_only",
    }
    assert result["signal_feed"]
    assert all(row["actionable"] is False for row in result["signal_feed"])
    assert all(row["execution"] == "paper_only" for row in result["signal_feed"])
    assert {row["source"] for row in result["signal_feed"]} == {"synthetic_demo"}
    assert any(row["classification"] == "historical_paper_fill"
               for row in result["signal_feed"])
    assert any(row["classification"] == "historical_rejection"
               for row in result["signal_feed"])
    assert path.read_bytes() == before


def test_signal_snapshot_scoped_to_requested_run(tmp_path: Path):
    path = tmp_path / "runs.sqlite"
    with IntelStore(path) as store:
        when = demo(CopyPaper(store, "demo"))
        CopyPaper(store, "empty")
    result = snapshot(path, "empty", now=when)
    assert result["recent_decisions"] == []
    assert result["signal_feed"] == []


def test_js_is_safe_and_uses_server_fields():
    script = Path("src/solana_ai_bot/web/app.js").read_text(encoding="utf-8")
    page = Path("src/solana_ai_bot/web/index.html").read_text(encoding="utf-8")
    assert "signal_feed" in script
    assert "paper-auto-info" in script
    assert 'id="signals-table"' in page
    assert 'id="paper-auto-info"' in page
    assert "innerHTML" not in script
    assert "eval(" not in script
