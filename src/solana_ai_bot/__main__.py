"""Use the same CLI for the console script and python -m solana_ai_bot."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
