import json

from solana_ai_bot import cli


def test_cli_backtest_reports_only_paper_results(tmp_path, capsys):
    source = tmp_path / "prices.csv"
    source.write_text(
        "mint,timestamp,price\n"
        "Demo,1,10\nDemo,2,9\nDemo,3,8\nDemo,4,10\n"
        "Demo,5,12\nDemo,6,14\nDemo,7,13\nDemo,8,11\n"
        "Demo,9,9\nDemo,10,8\n",
        encoding="utf-8",
    )
    assert cli.main(["backtest", "--prices", str(source), "--fast", "2", "--slow", "3"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["paper_only"] is True
    assert response["mint"] == "Demo"
    assert response["observation_count"] == 10
    assert len(response["result"]["closed_trades"]) == 1
    assert response["result"]["closed_trades"][0]["entered_at"] == 6
    assert response["result"]["closed_trades"][0]["exited_at"] == 9
