from .paper import simulate_round_trip


def main() -> None:
    result = simulate_round_trip(1.0, 1.1, 100.0)
    print(f"Illustrative net P&L: {result.net_pnl:.2f} units")
    print("Simulation only. No live prices, wallets or trades.")


if __name__ == "__main__":
    main()
