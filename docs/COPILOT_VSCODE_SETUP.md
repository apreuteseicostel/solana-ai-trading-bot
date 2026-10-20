# GitHub Copilot Agent Mode — controlled local setup

## What this enables
The **Copilot Agent Mode inside VS Code** can edit repository files, suggest shell commands, and run tests interactively while VS Code is open. It is distinct from GitHub Copilot's cloud coding agent. These instructions do not create a 24/7 autonomous runner, grant cloud agent privileges or start any trading.

## First-time desktop setup
1. Install/update [Visual Studio Code](https://code.visualstudio.com/).
2. Sign in with the GitHub account that owns this repository and has Copilot Free enabled. If prompted, install/enable GitHub Copilot and GitHub Copilot Chat (or use the built-in VS Code Copilot setup).
3. Clone `https://github.com/apreuteseicostel/solana-ai-trading-bot.git` using VS Code's **Git: Clone** command and open the resulting folder.
4. Use **Git: Checkout to...** to select branch `feature/copilot-agent-setup-20261020`. The current `main` branch does not yet contain the development modules or these instructions.
5. Open Copilot Chat and choose the **Agent** mode. Verify that the repository workspace is open.
6. Open `.github/copilot-instructions.md`. Copilot should use these repository-wide instructions automatically. Check references on an agent answer if available.
7. Type `/issue-6-hardening` into Chat (or paste the instructions from `.github/prompts/issue-6-hardening.prompt.md`). First request a plan and require confirmation before commands or commits.
8. Review every proposed command and code diff. Only allow safe commands such as `ruff check .` and `pytest -q`. Do not turn on unattended terminal approvals.
9. After successful local tests, create a separate work branch (e.g., `feature/issue-6-retry-budget`) and explicitly approve a commit/push if satisfied. Create a **Draft** PR against the appropriate unmerged development branch; do not merge.

## Suggested Git commands (optional alternative to VS Code menus)

```bash
git clone https://github.com/apreuteseicostel/solana-ai-trading-bot.git
cd solana-ai-trading-bot
git checkout feature/copilot-agent-setup-20261020
python -m pip install -e '.[dev]'
ruff check .
pytest -q
```

Do not put access tokens in the terminal, source files, repository issues, logs or Copilot Chat.

## Important distinctions
- `AGENTS.md` and `.github/copilot-instructions.md` provide advice; they do not trigger background work.
- `.github/prompts/issue-6-hardening.prompt.md` is reusable from VS Code Chat.
- The ChatGPT **Solana AutoDev — Issue #6** scheduled task is separate from GitHub Copilot; its ability to edit GitHub depends on tools available when it runs.
- Copilot Free has usage quotas and may not include Copilot cloud coding agent access.
- No real-price validation, live endpoint smoke test, wallet signing, unattended merges or real-money trades are provided by this setup.
