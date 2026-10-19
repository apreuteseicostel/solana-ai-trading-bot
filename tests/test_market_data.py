import pytest

from solana_ai_bot.market_data import load_price_csv


def test_load_price_csv(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text("mint,timestamp,price\nM1,1,10.0\nM1,2,12.0\n", encoding="utf-8")
    mint, ticks = load_price_csv(path)
    assert mint == "M1"
    assert [tick.price for tick in ticks] == [10.0, 12.0]


def test_reject_mixed_mints(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text("mint,timestamp,price\nM1,1,10\nM2,2,20\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one token"):
        load_price_csv(path)


def test_reject_oversized_input(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text("mint,timestamp,price\nM1,1,10\nM1,2,20\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_rows"):
        load_price_csv(path, max_rows=1)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "mint,price\nM,1\n",
        "mint,timestamp,price\n",
        "mint,timestamp,price\nM,no,1\n",
        "mint,timestamp,price\nM,1,invalid\n",
    ],
)
def test_bad_csv(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_price_csv(path)
